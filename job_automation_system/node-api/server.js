/**
 * Node.js API Server with Socket.io - Job Automation System
 * ============================================================
 * Production-ready API server with real-time WebSocket support.
 */

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const { MongoClient, ObjectId } = require('mongodb');
const Redis = require('ioredis');
const crypto = require('crypto');
require('dotenv').config();

// Docker Manager - for container lifecycle management
const { dockerManager } = require('./services/docker-manager');

// Auto-Stop Detector - for automatic worker shutdown
const { AutoStopDetector } = require('./services/auto-stop-detector');
let autoStopDetector = null;

// Auto-Start Scheduler - for automatic scheduled startup
const { AutoStartScheduler } = require('./services/auto-start-scheduler');
let autoStartScheduler = null;

const app = express();
const server = http.createServer(app);

// Socket.io setup with CORS (allow localhost development only)
const io = new Server(server, {
  cors: {
    origin: /^http:\/\/(localhost|127\.0\.0\.1):(3000|5173|5000)$/,
    methods: ["GET", "POST"]
  }
});

// Middleware
app.use(cors({
  origin: /^http:\/\/(localhost|127\.0\.0\.1):(3000|5173|5000)$/
}));
app.use(express.json());

// MongoDB connection
const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/job_automation';
const mongoClient = new MongoClient(MONGO_URI);

let db;
let applicationsCollection;
let studentsCollection;

async function connectDB() {
  try {
    await mongoClient.connect();
    const DB_NAME = process.env.MONGO_DB || 'ai_bot_resumes';
    db = mongoClient.db(DB_NAME);
    applicationsCollection = db.collection('job_applications');
    studentsCollection = db.collection('students');
    console.log(`âœ… Connected to MongoDB (Database: ${DB_NAME})`);
  } catch (error) {
    console.error('â Œ MongoDB connection error:', error);
    process.exit(1);
  }
}

// Redis connection
const redis = new Redis({
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
});

redis.on('connect', () => console.log('âœ… Connected to Redis'));
redis.on('error', (err) => console.error('â Œ Redis error:', err));

// ==================== Helper Functions ====================

// Emit to all connected clients
function emitApplicationUpdate(applicationData) {
  io.emit('newApplication', applicationData);
  console.log('ðŸ“¡ Emitted new application:', applicationData.platform, applicationData.jobTitle || applicationData.job_title);
}


function _metricLabels(labels = {}) {
  const keys = Object.keys(labels);
  if (!keys.length) return '';
  const parts = keys.map(
    (k) => `${k}="${String(labels[k]).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`
  );
  return `{${parts.join(",")}}`;
}

function _metricLine(name, value, labels = null) {
  if (!labels) return `${name} ${value}`;
  return `${name}${_metricLabels(labels)} ${value}`;
}

function normalizePlatformName(platformRaw = '') {
  const p = String(platformRaw || '').toLowerCase();
  if (p === 'linkedin') return 'LinkedIn';
  if (p === 'naukri') return 'Naukri';
  if (p === 'foundit') return 'Foundit';
  return platformRaw || 'Unknown';
}

/**
 * Build a Celery v2 protocol message for Redis broker.
 * Workers running Celery 4+ expect this exact wire format.
 */
function buildCeleryMessage(taskName, args = [], kwargs = {}, queue = 'producer') {
  const taskId = crypto.randomUUID();
  // Celery body = base64(JSON([args, kwargs, embed_dict]))
  const bodyRaw = JSON.stringify([args, kwargs, { callbacks: null, errbacks: null, chain: null, chord: null }]);
  const body = Buffer.from(bodyRaw).toString('base64');
  return JSON.stringify({
    body,
    'content-encoding': 'utf-8',
    'content-type': 'application/json',
    headers: {
      lang: 'py',
      task: taskName,
      id: taskId,
      shadow: null,
      eta: null,
      expires: null,
      group: null,
      group_index: null,
      chord: null,
      retries: 0,
      timelimit: [null, null],
      root_id: taskId,
      parent_id: null,
      argsrepr: JSON.stringify(args),
      kwargsrepr: JSON.stringify(kwargs),
      origin: 'node-api',
    },
    properties: {
      correlation_id: taskId,
      reply_to: crypto.randomUUID(),
      delivery_mode: 2,
      delivery_info: { exchange: '', routing_key: queue },
      priority: 0,
      body_encoding: 'base64',
      delivery_tag: crypto.randomUUID(),
    },
  });
}

function normalizeStatus(raw = '') {
  const s = String(raw || '').toLowerCase();
  if (s === 'applied') return 'applied';
  if (s === 'failed' || s === 'rejected') return 'failed';
  if (s === 'pending') return 'pending';
  if (s === 'skipped') return 'skipped';
  if (s === 'duplicate') return 'duplicate';
  return s || 'pending';
}

function getTimeframeStart(timeframe = 'all') {
  const now = Date.now();
  switch (String(timeframe || '').toLowerCase()) {
    case '24h':
    case 'last24h':
      return new Date(now - 24 * 60 * 60 * 1000);
    case '7d':
    case 'week':
      return new Date(now - 7 * 24 * 60 * 60 * 1000);
    case '15d':
      return new Date(now - 15 * 24 * 60 * 60 * 1000);
    case '1m':
    case 'month':
      return new Date(now - 30 * 24 * 60 * 60 * 1000);
    case '3m':
      return new Date(now - 90 * 24 * 60 * 60 * 1000);
    default:
      return null;
  }
}

function pickResumeUrl(student, variant = '') {
  if (!student || !student.resume_urls || !variant) return '';
  return student.resume_urls?.[variant] || '';
}

function toDashboardPayload(app, student = null) {
  const studentId = app.student_id || app.studentId || 'unknown';
  const studentName =
    app.studentName ||
    app.candidateName ||
    student?.name ||
    studentId;
  const studentEmail =
    app.candidateEmail ||
    student?.email ||
    '';
  const variant = app.resume_variant || app.resumeVariant || '';
  const resumeUrl = app.resume_url || app.resumeUrl || pickResumeUrl(student, variant);
  const rawStatus = app.rawStatus || app.status || 'pending';

  const normalized = {
    _id: String(app._id || app.id || `${studentId}-${Date.now()}`),
    studentId,
    studentName,
    candidateName: studentName,
    candidateEmail: studentEmail,
    role: app.role || app.job_title || app.jobTitle || 'N/A',
    jobTitle: app.job_title || app.jobTitle || app.role || 'N/A',
    company: app.company || 'N/A',
    platform: normalizePlatformName(app.platform || ''),
    status: normalizeStatus(rawStatus),
    rawStatus: rawStatus,
    appliedAt: app.appliedAt || (app.applied_at ? new Date(app.applied_at).toISOString() : (app.created_at ? new Date(app.created_at).toISOString() : new Date().toISOString())),
    resumeVariant: variant,
    resumeUrl: resumeUrl || '',
    jobUrl: app.job_url || app.jobUrl || '',
    error: app.error || app.error_message || null,
  };

  return normalized;
}
// ==================== API Routes ====================

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'job-automation-api',
    timestamp: new Date().toISOString()
  });
});


// Prometheus endpoint for Grafana dashboards (also available at /api/metrics)
app.get('/metrics', async (req, res) => {
  try {
    const platforms = ['naukri', 'linkedin', 'foundit'];
    const statuses = ['pending', 'applied', 'failed', 'skipped', 'duplicate'];
    const durationBuckets = [1, 2, 5, 10, 20, 30, 60, 120, 300, 600];

    const grouped = await applicationsCollection.aggregate([
      {
        $match: {
          platform: { $in: platforms }
        }
      },
      {
        $group: {
          _id: { platform: '$platform', status: '$status' },
          count: { $sum: 1 }
        }
      }
    ]).toArray();

    const counts = new Map();
    for (const row of grouped) {
      const platform = row?._id?.platform || 'unknown';
      const status = row?._id?.status || 'unknown';
      counts.set(`${platform}::${status}`, Number(row.count || 0));
    }

    // Duration source: created_at -> applied_at (or updated_at fallback), excluding pending.
    const durationDocs = await applicationsCollection.aggregate([
      {
        $match: {
          platform: { $in: platforms },
          status: { $ne: 'pending' },
          created_at: { $type: 'date' }
        }
      },
      {
        $project: {
          platform: 1,
          duration_seconds: {
            $divide: [
              { $subtract: [{ $ifNull: ['$applied_at', '$updated_at'] }, '$created_at'] },
              1000
            ]
          }
        }
      },
      {
        $match: {
          duration_seconds: { $gte: 0 }
        }
      },
      { $limit: 5000 }
    ]).toArray();

    const durationByPlatform = new Map();
    for (const platform of platforms) {
      durationByPlatform.set(platform, []);
    }
    for (const row of durationDocs) {
      const platform = row?.platform;
      const duration = Number(row?.duration_seconds);
      if (!platforms.includes(platform) || !Number.isFinite(duration)) continue;
      durationByPlatform.get(platform).push(duration);
    }

    const lines = [];
    lines.push('# HELP job_automation_tasks_total Total number of task outcomes by platform and status');
    lines.push('# TYPE job_automation_tasks_total counter');
    for (const platform of platforms) {
      for (const status of statuses) {
        const value = counts.get(`${platform}::${status}`) || 0;
        lines.push(_metricLine('job_automation_tasks_total', value, { platform, status }));
      }
    }

    lines.push('# HELP job_automation_applications_total Total number of application outcomes by platform and status');
    lines.push('# TYPE job_automation_applications_total counter');
    for (const platform of platforms) {
      for (const status of statuses) {
        const value = counts.get(`${platform}::${status}`) || 0;
        lines.push(_metricLine('job_automation_applications_total', value, { platform, status }));
      }
    }

    lines.push('# HELP job_automation_active_browsers Number of active browser instances');
    lines.push('# TYPE job_automation_active_browsers gauge');
    await redis.zremrangebyscore('semaphore:browsers:leases', 0, Date.now() / 1000);
    const activeBrowsers = await redis.zcard('semaphore:browsers:leases') || 0;
    lines.push(_metricLine('job_automation_active_browsers', activeBrowsers));

    lines.push('# HELP job_automation_queue_tasks Number of tasks in queue by platform');
    lines.push('# TYPE job_automation_queue_tasks gauge');
    for (const platform of platforms) {
      const pendingCount = counts.get(`${platform}::pending`) || 0;
      lines.push(_metricLine('job_automation_queue_tasks', pendingCount, { platform }));
    }

    lines.push('# HELP job_automation_circuit_state Circuit breaker state (0=closed,1=open,2=half-open)');
    lines.push('# TYPE job_automation_circuit_state gauge');
    for (const platform of platforms) {
      const state = await redis.get(`circuit:${platform}:state`) || 'closed';
      const stateVal = state === 'open' ? 1 : (state === 'half_open' ? 2 : 0);
      lines.push(_metricLine('job_automation_circuit_state', stateVal, { platform }));
    }

    lines.push('# HELP job_automation_task_duration_seconds Task duration histogram');
    lines.push('# TYPE job_automation_task_duration_seconds histogram');
    for (const platform of platforms) {
      const values = durationByPlatform.get(platform) || [];
      for (const le of durationBuckets) {
        const upToLe = values.filter((v) => v <= le).length;
        lines.push(_metricLine('job_automation_task_duration_seconds_bucket', upToLe, { platform, le }));
      }
      lines.push(_metricLine('job_automation_task_duration_seconds_bucket', values.length, { platform, le: '+Inf' }));
      const sum = values.reduce((acc, v) => acc + v, 0);
      lines.push(_metricLine('job_automation_task_duration_seconds_sum', sum, { platform }));
      lines.push(_metricLine('job_automation_task_duration_seconds_count', values.length, { platform }));
    }

    // Redis queue lengths
    const redisQueues = ['naukri', 'linkedin', 'foundit', 'producer', 'warmup'];
    let totalQueueLen = 0;
    lines.push('# HELP job_automation_queue_length Number of pending tasks in Redis by queue');
    lines.push('# TYPE job_automation_queue_length gauge');
    for (const queue of redisQueues) {
      const len = (await redis.llen(queue)) || 0;
      totalQueueLen += len;
      lines.push(_metricLine('job_automation_queue_length', len, { queue }));
    }

    // Total queue + jobs_completed_today + jobs_running from Redis
    lines.push('# HELP job_automation_jobs_completed_today Total jobs completed today');
    lines.push('# TYPE job_automation_jobs_completed_today gauge');
    const completedToday = parseInt(await redis.get('automation:jobs_completed_today') || '0');
    lines.push(_metricLine('job_automation_jobs_completed_today', completedToday));

    lines.push('# HELP job_automation_jobs_running Current number of running jobs');
    lines.push('# TYPE job_automation_jobs_running gauge');
    const jobsRunning = parseInt(await redis.get('automation:jobs_running') || '0');
    lines.push(_metricLine('job_automation_jobs_running', jobsRunning));

    lines.push('# HELP job_automation_queue_total Total pending tasks across all queues');
    lines.push('# TYPE job_automation_queue_total gauge');
    lines.push(_metricLine('job_automation_queue_total', totalQueueLen));

    // Idempotency failure counters (tracked via Redis)
    lines.push('# HELP job_automation_idemp_clear_failures_total Idempotency key clear failures');
    lines.push('# TYPE job_automation_idemp_clear_failures_total counter');
    const idempClearFailures = parseInt(await redis.get('job_automation:idemp_clear_failures') || '0');
    lines.push(_metricLine('job_automation_idemp_clear_failures_total', idempClearFailures));

    lines.push('# HELP job_automation_session_clear_failures_total Session key clear failures');
    lines.push('# TYPE job_automation_session_clear_failures_total counter');
    const sessionClearFailures = parseInt(await redis.get('job_automation:session_clear_failures') || '0');
    lines.push(_metricLine('job_automation_session_clear_failures_total', sessionClearFailures));

    // Rate limiter timeout counter
    lines.push('# HELP job_automation_rate_limit_timeouts_total Rate limiter timeouts');
    lines.push('# TYPE job_automation_rate_limit_timeouts_total counter');
    const rateLimitTimeouts = parseInt(await redis.get('job_automation:rate_limit_timeouts') || '0');
    lines.push(_metricLine('job_automation_rate_limit_timeouts_total', rateLimitTimeouts));

    res.set('Content-Type', 'text/plain; version=0.0.4; charset=utf-8');
    res.send(`${lines.join('\n')}\n`);
  } catch (error) {
    console.error('Metrics error:', error);
    res.status(500).send(`# metrics_error ${error.message}\n`);
  }
});
app.get('/api/metrics', (req, res, next) => {
  req.url = '/metrics';
  next();
});
// Get all applications with optional timeframe filter
app.get('/api/applications', async (req, res) => {
  try {
    const { timeframe = 'all' } = req.query;
    
    // Build query
    let query = {};
    const startDate = getTimeframeStart(timeframe);
    if (startDate) {
      query = {
        $or: [
          { applied_at: { $gte: startDate } },
          { updated_at: { $gte: startDate } },
          { created_at: { $gte: startDate } },
        ]
      };
    }
    
    // Fetch applications
    const applications = await applicationsCollection
      .find(query)
      .sort({ created_at: -1, applied_at: -1 })
      .limit(500)
      .toArray();
    
    // Transform for frontend
    const studentIds = [...new Set(applications.map(app => app.student_id).filter(Boolean))];
    const students = studentIds.length
      ? await studentsCollection.find({ student_id: { $in: studentIds } }).toArray()
      : [];
    const studentMap = new Map(students.map(student => [student.student_id, student]));
    const result = applications.map(app => toDashboardPayload(app, studentMap.get(app.student_id) || null));
    
    res.json(result);
  } catch (error) {
    console.error('Error fetching applications:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get application statistics
app.get('/api/stats', async (req, res) => {
  try {
    const total = await applicationsCollection.countDocuments({});
    const applied = await applicationsCollection.countDocuments({ status: 'applied' });
    const failed = await applicationsCollection.countDocuments({ status: 'failed' });
    const pending = await applicationsCollection.countDocuments({ status: 'pending' });
    
    // By platform
    const platformCounts = await applicationsCollection.aggregate([
      { $group: { _id: '$platform', count: { $sum: 1 } } }
    ]).toArray();
    
    const platforms = platformCounts.reduce((acc, p) => {
      acc[p._id] = p.count;
      return acc;
    }, {});
    
    const skipped = await applicationsCollection.countDocuments({ status: 'skipped' });
    const duplicate = await applicationsCollection.countDocuments({ status: 'duplicate' });
    const totalStudents = await studentsCollection.countDocuments({ active: true });
    const successRate = total > 0 ? ((applied / total) * 100).toFixed(1) : '0.0';

    res.json({
      total,
      applied,
      failed,
      pending,
      skipped,
      duplicate,
      totalStudents,
      successRate,
      platforms
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    res.status(500).json({ error: error.message });
  }
});

// Chart data — daily applied/failed grouped by date
app.get('/api/stats/chart', async (req, res) => {
  try {
    const { timeframe = '7d' } = req.query;
    const startDate = getTimeframeStart(timeframe);
    
    // Improved match: look at either applied_at or created_at
    const match = startDate ? {
      $or: [
        { applied_at: { $gte: startDate } },
        { created_at: { $gte: startDate } }
      ]
    } : {};

    const pipeline = [
      { $match: match },
      {
        $group: {
          _id: {
            date: { $dateToString: { format: '%Y-%m-%d', date: { $ifNull: ['$applied_at', '$created_at'] } } },
            status: '$status'
          },
          count: { $sum: 1 }
        }
      },
      { $sort: { '_id.date': 1 } }
    ];

    const rows = await applicationsCollection.aggregate(pipeline).toArray();

    // Pivot into { date, applied, failed, skipped, pending }
    const dateMap = {};
    for (const row of rows) {
      const d = row._id?.date || 'unknown';
      const s = row._id?.status || 'unknown';
      if (!dateMap[d]) dateMap[d] = { date: d, applied: 0, failed: 0, skipped: 0, pending: 0, total: 0 };
      dateMap[d][s] = (dateMap[d][s] || 0) + row.count;
      dateMap[d].total += row.count;
    }

    const result = Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));
    res.json(result);
  } catch (error) {
    console.error('Error fetching chart data:', error);
    res.status(500).json({ error: error.message });
  }
});

// Platform distribution
app.get('/api/stats/platforms', async (req, res) => {
  try {
    const pipeline = [
      { $group: { _id: '$platform', total: { $sum: 1 }, applied: { $sum: { $cond: [{ $eq: ['$status', 'applied'] }, 1, 0] } }, failed: { $sum: { $cond: [{ $eq: ['$status', 'failed'] }, 1, 0] } } } },
      { $sort: { total: -1 } }
    ];
    const rows = await applicationsCollection.aggregate(pipeline).toArray();
    const result = rows.map(r => ({
      name: normalizePlatformName(r._id),
      total: r.total,
      applied: r.applied,
      failed: r.failed,
    }));
    res.json(result);
  } catch (error) {
    console.error('Error fetching platform stats:', error);
    res.status(500).json({ error: error.message });
  }
});

// System health for settings page
app.get('/api/system/health', async (req, res) => {
  try {
    const activeBrowsers = parseInt(await redis.get('semaphore:browsers') || '0');
    const circuitStates = {};
    for (const p of ['naukri', 'linkedin', 'foundit']) {
      circuitStates[p] = (await redis.get(`circuit:${p}:state`)) || 'closed';
    }
    const redisInfo = await redis.info('memory');
    const memMatch = redisInfo.match(/used_memory_human:(\S+)/);

    res.json({
      status: 'healthy',
      activeBrowsers,
      circuitStates,
      redisMemory: memMatch ? memMatch[1] : 'N/A',
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    res.status(500).json({ status: 'unhealthy', error: error.message });
  }
});

// Get all students
app.get('/api/students', async (req, res) => {
  try {
    const students = await studentsCollection
      .find({})
      .limit(100)
      .toArray();
    
    console.log(`ðŸ” Found ${students.length} students in database`);
    
    const result = students.map(s => ({
      _id: s._id.toString(),
      student_id: s.student_id,
      name: s.name,
      email: s.email,
      phone: s.phone || s.mobile || 'N/A',
      primary_role: s.primary_role || 'N/A',
      candidate_titles: s.candidate_titles || [],
      active: s.active
    }));
    
    res.json(result);
  } catch (error) {
    console.error('Error fetching students:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get specific student
app.get('/api/students/:student_id', async (req, res) => {
  try {
    const { student_id } = req.params;
    const student = await studentsCollection.findOne({ student_id });
    
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    
    // Get applications for this student
    const apps = await applicationsCollection
      .find({ student_id })
      .sort({ created_at: -1, applied_at: -1 })
      .toArray();
    
    res.json({
      _id: student._id.toString(),
      student_id: student.student_id,
      name: student.name,
      email: student.email,
      phone: student.phone,
      location: student.location,
      skills: student.skills || [],
      primary_role: student.primary_role || 'N/A',
      custom_roles: student.custom_roles || {},
      candidate_titles: student.candidate_titles || [],
      applications: apps.map(a => ({
        platform: a.platform,
        job_title: a.jobTitle || a.job_title,
        company: a.company,
        status: a.status,
        applied_at: a.appliedAt || a.applied_at || a.createdAt || a.created_at,
      }))
    });
  } catch (error) {
    console.error('Error fetching student:', error);
    res.status(500).json({ error: error.message });
  }
});

// Notify endpoint - for Celery workers to notify when application is completed
app.post('/api/notify-application', async (req, res) => {
  try {
    const data = req.body;
    
    if (!data) {
      return res.status(400).json({ error: 'No data provided' });
    }
    
    let student = null;
    if (data.studentId) {
      student = await studentsCollection.findOne({ student_id: data.studentId });
    }
    const payload = toDashboardPayload({
      ...data,
      student_id: data.studentId,
      job_title: data.jobTitle,
      resume_variant: data.resumeVariant,
      resume_url: data.resumeUrl,
      job_url: data.jobUrl,
      applied_at: data.appliedAt,
    }, student);

    // Save to MongoDB for persistence
    const normalizedStatus = normalizeStatus(data.status || 'pending');
    await applicationsCollection.insertOne({
      ...payload,
      status: normalizedStatus,
      created_at: new Date(),
    });
    
    // Emit to all connected clients
    emitApplicationUpdate(payload);
    
    res.json({ status: 'success', message: 'Notification sent' });
  } catch (error) {
    console.error('Error sending notification:', error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== WebSocket Events ====================

io.on('connection', (socket) => {
  console.log(`âœ… Client connected: ${socket.id}`);
  
  socket.on('disconnect', () => {
    console.log(`âŒ Client disconnected: ${socket.id}`);
  });
});

// ==================== Auto-Stop Detector Init ====================

function initAutoStop() {
  autoStopDetector = new AutoStopDetector(redis, db);
  autoStopDetector.setSocketIO(io);
  
  redis.get('automation:auto_stop').then(val => {
    if (val === 'true') {
      autoStopDetector.start();
      console.log('[AutoStop] Detector active (auto-stop enabled)');
    } else {
      console.log('[AutoStop] Detector standby (auto-stop disabled)');
    }
  });
}

function initAutoStartScheduler() {
  autoStartScheduler = new AutoStartScheduler(redis, io);
  autoStartScheduler.start();
  console.log('[AutoStart] Scheduler initialized');
}

// ==================== Start Server ====================

const PORT = process.env.PORT || 5000;

async function startServer() {
  await connectDB();
  
  initAutoStop();
  initAutoStartScheduler();
  
  server.listen(PORT, '0.0.0.0', () => {
    console.log(`ðŸš€ Job Automation API running on port ${PORT}`);
    console.log(`   Socket.io enabled for real-time updates`);
  });
}

// AI Engine Settings Endpoint
app.get('/api/settings/ai-engine', async (req, res) => {
  try {
    const aiEnabled = process.env.AI_ENGINE_ENABLED !== 'false';
    res.json({ enabled: aiEnabled });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/settings/ai-engine', async (req, res) => {
  try {
    const { enabled } = req.body;
    // Note: In production, you'd update Redis or a config store
    // For now, just return the current state (actual toggle requires worker restart)
    res.json({ 
      enabled, 
      message: 'Workers must be restarted for change to take effect. Use: AI_ENGINE_ENABLED=' + enabled + ' pm2 restart all'
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ==================== Automation Toggle API ====================

// Get automation status - INCLUDING CONTAINER STATUS
app.get('/api/automation/status', async (req, res) => {
  try {
    const [mainSwitch, autoEnable, lastToggleTime, jobsRunning, jobsCompletedToday, autoOffTime, dailySchedule, workersUp, autoStop, lastStartTime] = await Promise.all([
      redis.get('automation:main_switch'),
      redis.get('automation:auto_enable'),
      redis.get('automation:last_toggle_time'),
      redis.get('automation:jobs_running'),
      redis.get('automation:jobs_completed_today'),
      redis.get('automation:auto_off_time'),
      redis.get('automation:daily_schedule'),
      redis.get('automation:workers_up'),
      redis.get('automation:auto_stop'),
      redis.get('automation:last_start_time')
    ]);
    
    let workerStatus = null;
    try {
      const dockerCheck = await dockerManager.isDockerAvailable();
      if (dockerCheck.available) {
        workerStatus = await dockerManager.getWorkerStatus();
      }
    } catch (e) {
      console.log('[API] Worker status check failed:', e.message);
    }
    
    res.json({
      main_switch: mainSwitch || 'off',
      workers_up: workersUp || 'false',
      auto_enable: autoEnable === 'true',
      auto_stop: autoStop === 'true',
      last_toggle_time: lastToggleTime,
      last_start_time: lastStartTime,
      jobs_running: parseInt(jobsRunning) || 0,
      jobs_completed_today: parseInt(jobsCompletedToday) || 0,
      auto_off_time: autoOffTime || '23:59',
      daily_schedule: dailySchedule || '06:00,11:00,17:00',
      workers: workerStatus ? {
        total: workerStatus.totalWorkers,
        running: workerStatus.runningWorkers,
        infra: workerStatus.infra,
        workers: workerStatus.workers
      } : null,
      docker_available: workerStatus !== null,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Auto-stop toggle
app.post('/api/automation/auto-stop', async (req, res) => {
  try {
    const { enabled } = req.body;
    await redis.set('automation:auto_stop', enabled ? 'true' : 'false');
    
    if (autoStopDetector) {
      if (enabled) {
        autoStopDetector.start();
      } else {
        autoStopDetector.stop();
      }
    }
    
    res.json({ success: true, auto_stop: enabled ? 'true' : 'false' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Toggle automation on/off - WITH DOCKER CONTAINER MANAGEMENT
app.post('/api/automation/toggle', async (req, res) => {
  try {
    const { status, auto_enable } = req.body;
    
    const newStatus = status === 'on' ? 'on' : 'off';
    
    if (newStatus === 'on') {
      console.log('[API] START triggered - starting all containers...');
      
      const dockerCheck = await dockerManager.isDockerAvailable();
      if (!dockerCheck.available) {
        return res.status(503).json({ 
          error: 'Docker is not running. Please start Docker Desktop.',
          code: 'DOCKER_NOT_RUNNING'
        });
      }
      
      const startResult = await dockerManager.startAll();
      
      if (!startResult.success && !startResult.workersStarted?.length) {
        return res.status(500).json({ 
          error: startResult.error || 'Failed to start workers',
          code: 'CONTAINER_START_FAILED',
          failedContainers: startResult.workersFailed
        });
      }
      
      await redis.set('automation:main_switch', 'on');
      await redis.set('automation:workers_up', 'true');
      await redis.set('automation:jobs_running', '0');
      await redis.set('automation:jobs_queue', '0');
      
      if (auto_enable !== undefined) {
        await redis.set('automation:auto_enable', auto_enable ? 'true' : 'false');
      }
      
      const startTime = new Date().toISOString();
      await redis.set('automation:last_toggle_time', startTime);
      await redis.set('automation:last_start_time', startTime);
      await redis.set('automation:jobs_completed_today', '0');
      await redis.set('automation:auto_stop', 'true');
      await redis.set('automation:auto_stop_reason', '');
      
      if (autoStopDetector) {
        autoStopDetector.recordStart();
        if (!autoStopDetector.isActive()) {
          autoStopDetector.start();
        }
      }
      
      const workerStatus = await dockerManager.getWorkerStatus();
      
      console.log('[API] START successful');
      res.json({
        success: true,
        main_switch: 'on',
        workers_up: 'true',
        message: `Started ${startResult.workersStarted?.length || 0} workers, ${startResult.workersAlreadyRunning?.length || 0} already running`,
        infraStarted: startResult.infraStarted,
        workersStarted: startResult.workersStarted,
        workersAlreadyRunning: startResult.workersAlreadyRunning,
        workersFailed: startResult.workersFailed,
        workerStatus: workerStatus,
        timestamp: startTime
      });
      
    } else {
      console.log('[API] STOP triggered - stopping workers...');
      
      const jobsRunning = parseInt(await redis.get('automation:jobs_running') || '0', 10);
      
      const stopResult = await dockerManager.stopWorkers();
      
      await redis.set('automation:main_switch', 'off');
      await redis.set('automation:workers_up', 'false');
      
      const stopTime = new Date().toISOString();
      await redis.set('automation:last_toggle_time', stopTime);
      await redis.set('automation:stop_reason', 'manual');
      
      if (autoStopDetector) {
        autoStopDetector.resetStableTimer();
      }
      
      console.log('[API] STOP completed');
      res.json({
        success: true,
        main_switch: 'off',
        workers_up: 'false',
        message: `${stopResult.stopped?.length || 0} workers stopped, ${stopResult.alreadyStopped?.length || 0} already stopped`,
        workersStopped: stopResult.stopped,
        workersAlreadyStopped: stopResult.alreadyStopped,
        workersFailed: stopResult.failed,
        hasFailures: stopResult.hasFailures,
        timestamp: stopTime
      });
    }
  } catch (error) {
    console.error('[API] Toggle error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Update automation settings
app.post('/api/automation/settings', async (req, res) => {
  try {
    const { auto_off_time, daily_schedule, auto_enable } = req.body;
    
    if (auto_off_time) {
      await redis.set('automation:auto_off_time', auto_off_time);
    }
    
    if (daily_schedule) {
      await redis.set('automation:daily_schedule', daily_schedule);
    }
    
    if (auto_enable !== undefined) {
      await redis.set('automation:auto_enable', auto_enable ? 'true' : 'false');
    }
    
    const current_auto_off_time = await redis.get('automation:auto_off_time');
    const current_daily_schedule = await redis.get('automation:daily_schedule');
    const current_auto_enable = await redis.get('automation:auto_enable');
    
    res.json({
      success: true,
      message: 'Automation settings updated',
      settings: {
        auto_off_time: current_auto_off_time || '23:59',
        daily_schedule: current_daily_schedule || '06:00,11:00,17:00',
        auto_enable: current_auto_enable === 'true'
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update jobs running count
app.post('/api/automation/jobs-count', async (req, res) => {
  try {
    const { jobs_running, jobs_completed_today } = req.body;
    
    if (jobs_running !== undefined) {
      await redis.set('automation:jobs_running', jobs_running.toString());
    }
    
    if (jobs_completed_today !== undefined) {
      await redis.set('automation:jobs_completed_today', jobs_completed_today.toString());
    }
    
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Trigger a job application run
// Accepts optional body: { jobs_per_student, student_limit, platforms, schedule_name }
// Default: 2 jobs per student, all students, all 3 platforms
app.post('/api/automation/run', async (req, res) => {
  try {
    const mainSwitch = await redis.get('automation:main_switch');

    if (mainSwitch !== 'on') {
      return res.status(400).json({ error: 'Automation is not enabled. Press START first.' });
    }

    // Configurable — defaults tuned for 3-student test (2 jobs each)
    const jobs_per_student = parseInt(req.body?.jobs_per_student) || 5; // match JOBS_PER_WAVE=5 in .env
    const student_limit   = parseInt(req.body?.student_limit)    || 0; // 0 = all active students
    const platforms       = req.body?.platforms || ['naukri', 'linkedin', 'foundit'];
    const schedule_name   = req.body?.schedule_name || 'manual-run';

    await redis.set('automation:jobs_running', String(student_limit || 'all'));

    // Build proper Celery v2 protocol message — workers running Celery 4+ require this format
    const taskMsg = buildCeleryMessage(
      'tasks.producer_beat_task.run_producer',
      [],
      { jobs_per_student, student_limit, platforms, schedule_name },
      'producer'
    );

    // Push to Redis key = queue name ('producer')
    // FIX: was 'celery producer' (space = wrong key) — now correctly 'producer'
    await redis.rpush('producer', taskMsg);

    console.log(`[API] RUN triggered → students: ${student_limit || 'all'}, jobs: ${jobs_per_student}, platforms: ${platforms.join(', ')}`);

    res.json({
      success: true,
      message: `Job run triggered: ${jobs_per_student} jobs/student on ${platforms.join(', ')}`,
      jobs_per_student,
      student_limit: student_limit || 'all',
      platforms,
      wave_mode: true,
      note: 'Wave mode: time-based platform weights + 30-60s student spacing (anti-detection)'
    });
  } catch (error) {
    console.error('[API] Run error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Clear old applications to allow fresh applications  
app.post('/api/automation/clear-duplicates', async (req, res) => {
  try {
    const status = await redis.get('automation:main_switch');
    if (status !== 'on') {
      return res.status(400).json({ error: 'Automation is not enabled' });
    }
    
    // Clear Redis idempotency keys
    const keys = await redis.keys('idemp:*');
    for (const key of keys) {
      await redis.del(key);
    }
    const redisCount = keys.length;
    
    // Also clear applications from MongoDB to get fresh runs
    const MongoClient = require('mongodb').MongoClient;
    const mongoClient = new MongoClient(process.env.MONGO_URI || 'mongodb+srv://kosurivenky:venkyyamuna@cluster0.uhbfag1.mongodb.net/ai_bot_resumes?appName=Cluster0');
    await mongoClient.connect();
    const db = mongoClient.db('ai_bot_resumes');
    
    // Delete old successful applications (keep failed/pending)
    const result = await db.collection('job_applications').deleteMany({
      status: { $in: ['applied', 'skipped', 'duplicate'] }
    });
    
    await mongoClient.close();
    
    res.json({ 
      success: true, 
      message: `Cleared ${redisCount} Redis keys and ${result.deletedCount} MongoDB applications. Fresh jobs will be applied.`
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Record beat trigger time - called by beat task before submitting jobs
app.post('/api/automation/record-beat-trigger', async (req, res) => {
  try {
    const schedule_name = req.body?.schedule_name || 'unknown';
    await redis.set('automation:beat_last_trigger_time', Date.now().toString());
    await redis.set('automation:beat_last_schedule', schedule_name);
    console.log(`[API] Beat trigger recorded: ${schedule_name}`);
    res.json({ success: true, schedule_name });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Auth Routes
const jwt = require('jsonwebtoken');
const JWT_SECRET = process.env.JWT_SECRET || 'default-secret-key';

const asyncHandler = (fn) => (req, res, next) =>
  Promise.resolve(fn(req, res, next)).catch(next);

const authMiddleware = async (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ success: false, message: 'No token provided' });
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = decoded;
    next();
  } catch (error) {
    res.status(401).json({ success: false, message: 'Invalid token' });
  }
};

// POST /api/auth/register
app.post('/api/auth/register', asyncHandler(async (req, res) => {
  const { name, email, phone, password, gender } = req.body;
  if (!name || !email || !phone || !password || !gender) {
    return res.status(400).json({ success: false, message: 'Please provide all required fields.' });
  }
  const existing = await db.collection('students').findOne({ email });
  if (existing) {
    return res.status(400).json({ success: false, message: 'Email already registered.' });
  }
  const student_id = 'student_' + crypto.createHash('md5').update(email).digest('hex').substring(0, 8);
  const result = await db.collection('students').insertOne({
    student_id, name, email, phone, gender,
    credentials: { linkedin: {}, naukri: {}, foundit: {} },
    status: 'active', created_at: new Date()
  });
  const token = jwt.sign({ studentId: student_id, email }, JWT_SECRET, { expiresIn: '7d' });
  res.status(201).json({ success: true, message: 'Registration successful', token, student: { student_id, name, email } });
}));

// POST /api/auth/login
app.post('/api/auth/login', asyncHandler(async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ success: false, message: 'Please provide email and password.' });
  }
  const student = await db.collection('students').findOne({ email });
  if (!student) {
    return res.status(401).json({ success: false, message: 'Invalid credentials.' });
  }
  const token = jwt.sign({ studentId: student.student_id, email: student.email }, JWT_SECRET, { expiresIn: '7d' });
  res.json({ success: true, message: 'Login successful', token, student: { student_id: student.student_id, name: student.name, email: student.email } });
}));

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('\nðŸ›‘ Shutting down...');
  await mongoClient.close();
  server.close(() => {
    console.log('âœ… Server closed');
    process.exit(0);
  });
});

startServer();
