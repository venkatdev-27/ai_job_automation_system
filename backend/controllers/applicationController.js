const Application = require('../models/Application');

// Helper to get socket.io instance (will be attached to app in server.js)
const getIO = (req) => req.app.get('socketio');

const PLATFORM_MAP = {
  linkedin: 'LinkedIn',
  naukri: 'Naukri',
  foundit: 'Foundit',
};

const STATUS_MAP = {
  applied: 'applied',
  interviewing: 'interviewing',
  accepted: 'accepted',
  rejected: 'rejected',
  failed: 'failed',
  pending: 'pending',
  skipped: 'skipped',
  duplicate: 'duplicate',
};

function normalizePlatform(platform) {
  const key = String(platform || '').trim().toLowerCase();
  return PLATFORM_MAP[key] || 'LinkedIn';
}

function normalizeStatus(status) {
  const key = String(status || '').trim().toLowerCase();
  return STATUS_MAP[key] || 'applied';
}

function normalizeTimestamp(value) {
  if (!value || value === '__auto__') return new Date();
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return new Date();
  return parsed;
}

function buildApplicationPayload(body = {}) {
  const jobTitle = String(body.jobTitle || body.role || body.title || '').trim() || 'Unknown Role';
  const company = String(body.company || '').trim() || 'Unknown Company';

  const payload = {
    studentId: body.studentId || body.student_id || undefined,
    jobTitle,
    company,
    candidateName: String(body.candidateName || body.studentName || '').trim(),
    candidateEmail: String(body.candidateEmail || '').trim().toLowerCase(),
    location: String(body.location || '').trim(),
    platform: normalizePlatform(body.platform),
    status: normalizeStatus(body.status),
    resumeUrl: String(body.resumeUrl || '').trim(),
    jobDescription: String(body.jobDescription || '').trim(),
    atsScore: Number.isFinite(Number(body.atsScore)) ? Number(body.atsScore) : undefined,
    appliedAt: normalizeTimestamp(body.appliedAt || body.timestamp),
    jobUrl: String(body.jobUrl || '').trim(),
    sourceJobId: String(body.sourceJobId || body.job_id || body.jobId || '').trim(),
  };

  if (!payload.studentId) {
    delete payload.studentId;
  }
  if (payload.atsScore === undefined) {
    delete payload.atsScore;
  }

  return payload;
}

const getAllApplications = async (req, res) => {
  try {
    const { timeframe } = req.query;
    let query = {};

    if (timeframe && timeframe !== 'all') {
      const now = new Date();
      let startDate;
      if (timeframe === 'week') {
        startDate = new Date(now.setDate(now.getDate() - 7));
      } else if (timeframe === 'month') {
        startDate = new Date(now.setMonth(now.getMonth() - 1));
      }
      if (startDate) {
        query.createdAt = { $gte: startDate };
      }
    }

    const apps = await Application.find(query)
      .populate('studentId', 'name email')
      .sort({ createdAt: -1 });
    res.json(apps);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

const getApplicationById = async (req, res) => {
  try {
    const app = await Application.findById(req.params.id).populate('studentId', 'name email');
    if (!app) return res.status(404).json({ error: 'Application not found' });
    res.json(app);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

const createApplication = async (req, res) => {
  try {
    const payload = buildApplicationPayload(req.body);
    const application = await Application.create(payload);
    const populatedApplication = await Application.findById(application._id)
      .populate('studentId', 'name email');
    
    // Emit live update
    const io = getIO(req);
    if (io) {
      io.emit('newApplication', populatedApplication || application);
      
      // Get updated stats and emit
      const stats = await Application.aggregate([
        { $group: { _id: "$platform", count: { $sum: 1 } } }
      ]);
      io.emit('statsUpdated', stats);
    }

    res.status(201).json(populatedApplication || application);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
};

const logAutomationApplication = async (req, res) => {
  return createApplication(req, res);
};

const getDashboardStats = async (req, res) => {
  try {
    const { timeframe } = req.query;
    let query = {};

    if (timeframe && timeframe !== 'all') {
      const now = new Date();
      let startDate;
      if (timeframe === 'week') {
        startDate = new Date(now.setDate(now.getDate() - 7));
      } else if (timeframe === 'month') {
        startDate = new Date(now.setMonth(now.getMonth() - 1));
      }
      if (startDate) {
        query.createdAt = { $gte: startDate };
      }
    }

    const totalApplications = await Application.countDocuments(query);
    const platformStats = await Application.aggregate([
      { $match: query },
      { $group: { _id: "$platform", count: { $sum: 1 } } }
    ]);
    const recentApplications = await Application.find(query)
      .sort({ createdAt: -1 })
      .limit(5);

    res.json({
      totalApplications,
      platformStats,
      recentApplications,
      period: timeframe || 'all'
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};

const updateApplication = async (req, res) => {
  try {
    const app = await Application.findByIdAndUpdate(req.params.id, req.body, { new: true });
    res.json(app);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
};

const deleteApplication = async (req, res) => {
  try {
    await Application.findByIdAndDelete(req.params.id);
    res.json({ message: 'Application deleted' });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
};

module.exports = {
  getAllApplications,
  getApplicationById,
  createApplication,
  logAutomationApplication,
  updateApplication,
  deleteApplication,
  getDashboardStats,
};
