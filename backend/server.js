const express = require('express');
const cors = require('cors');
const path = require('path');
const http = require('http');
const socketIo = require('socket.io');
require('dotenv').config();

const connectDB = require('./config/db');
const { PORT } = require('./config/env');
const { extractResumeText } = require('./services/resumeTextExtractor');
const { ingestResumeTextToVectorDb } = require('./services/ragIngestService');
const { matchResumeWithQuery } = require('./services/ragMatcherService');
const { v2: cloudinary } = require('cloudinary');
const multer = require('multer');
const os = require('os');
const fsPromises = require('fs/promises');

const studentRoutes = require('./routes/studentRoutes');
const jobRoutes = require('./routes/jobRoutes');
const applicationRoutes = require('./routes/applicationRoutes');
const authRoutes = require('./routes/authRoutes');
const { logAutomationApplication } = require('./controllers/applicationController');
const matchRoutes = require('./routes/matchRoutes');
const errorMiddleware = require('./middleware/errorMiddleware');

// Connect to MongoDB
connectDB();

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "*", // Adjust for production
    methods: ["GET", "POST"]
  }
});

// Attach socketio to app for use in controllers
app.set('socketio', io);

io.on('connection', (socket) => {
  console.log('New client connected');
  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

// Core Middleware
app.use(cors());
app.use(express.json());

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});

const maxResumeSizeMb = Number(process.env.MAX_RESUME_SIZE_MB || 10);
const resumeUpload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: maxResumeSizeMb * 1024 * 1024,
  },
});

const allowedResumeExtensions = new Set(['.pdf', '.docx', '.doc']);

function buildResumeId(originalName, explicitResumeId) {
  if (explicitResumeId && explicitResumeId.trim()) {
    return explicitResumeId.trim();
  }

  const base = path.parse(originalName || 'resume').name || 'resume';
  const safeBase = base.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 80) || 'resume';
  return `${safeBase}_${Date.now()}`;
}

app.post('/api/resume/extract-text', async (req, res) => {
  try {
    const { filePath, originalName } = req.body || {};

    if (!filePath) {
      return res.status(400).json({ error: 'filePath is required' });
    }

    const text = await extractResumeText(filePath, originalName || '');
    return res.json({ text });
  } catch (error) {
    return res.status(500).json({
      error: 'Failed to extract resume text',
      details: error.message,
    });
  }
});

app.post('/api/resume/upload-and-index', resumeUpload.single('resume'), async (req, res) => {
  let tempFilePath;

  try {
    if (!req.file) {
      return res.status(400).json({ error: 'resume file is required (form field name: resume)' });
    }

    const originalName = req.file.originalname || 'resume';
    const extension = path.extname(originalName || '').toLowerCase();
    if (!allowedResumeExtensions.has(extension)) {
      return res.status(400).json({
        error: 'Unsupported file type. Allowed: .pdf, .docx, .doc',
      });
    }

    const resumeId = buildResumeId(originalName, req.body?.resumeId);
    const cloudinaryFolder = process.env.CLOUDINARY_FOLDER || 'ai_bot_resumes/resumes';

    const tempDir = path.join(os.tmpdir(), 'ai-bot-resume-uploads');
    await fsPromises.mkdir(tempDir, { recursive: true });
    tempFilePath = path.join(
      tempDir,
      `${Date.now()}_${Math.random().toString(36).slice(2)}${extension}`
    );
    await fsPromises.writeFile(tempFilePath, req.file.buffer);

    const uploadResult = await cloudinary.uploader.upload(tempFilePath, {
      resource_type: 'raw',
      folder: cloudinaryFolder,
      use_filename: true,
      unique_filename: true,
      filename_override: originalName,
    });

    const text = await extractResumeText(tempFilePath, originalName);
    if (!text || !text.trim()) {
      return res.status(400).json({
        error: 'No extractable text found in uploaded file',
      });
    }

    const chunkSize = req.body?.chunkSize ? Number(req.body.chunkSize) : undefined;
    const chunkOverlap = req.body?.chunkOverlap ? Number(req.body.chunkOverlap) : undefined;
    const replaceExisting = String(req.body?.replaceExisting ?? 'true').toLowerCase() !== 'false';

    const ingestResult = await ingestResumeTextToVectorDb({
      resumeId,
      text,
      sourceName: originalName,
      replaceExisting,
      chunkSize,
      chunkOverlap,
    });

    return res.status(201).json({
      resumeId,
      originalName,
      cloudinary: {
        secureUrl: uploadResult.secure_url,
        publicId: uploadResult.public_id,
        resourceType: uploadResult.resource_type,
        format: uploadResult.format,
      },
      indexing: ingestResult,
      extractedChars: text.length,
    });
  } catch (error) {
    return res.status(500).json({
      error: 'Failed to upload and index resume',
      details: error.message,
    });
  } finally {
    if (tempFilePath) {
      await fsPromises.unlink(tempFilePath).catch(() => {});
    }
  }
});

app.post('/api/resume/index-text', async (req, res) => {
  try {
    const {
      resumeId,
      text,
      sourceName,
      replaceExisting = true,
      chunkSize,
      chunkOverlap,
    } = req.body || {};

    if (!text || !text.trim()) {
      return res.status(400).json({ error: 'text is required' });
    }

    const result = await ingestResumeTextToVectorDb({
      resumeId,
      text,
      sourceName,
      replaceExisting,
      chunkSize,
      chunkOverlap,
    });

    return res.json(result);
  } catch (error) {
    return res.status(500).json({
      error: 'Failed to index resume text',
      details: error.message,
    });
  }
});

app.post('/api/resume/index-file', async (req, res) => {
  try {
    const {
      resumeId,
      filePath,
      originalName,
      sourceName,
      replaceExisting = true,
      chunkSize,
      chunkOverlap,
    } = req.body || {};

    if (!filePath || !filePath.trim()) {
      return res.status(400).json({ error: 'filePath is required' });
    }

    const text = await extractResumeText(filePath, originalName || '');
    if (!text || !text.trim()) {
      return res.status(400).json({ error: 'No extractable text found in file' });
    }

    const result = await ingestResumeTextToVectorDb({
      resumeId,
      text,
      sourceName: sourceName || originalName || filePath,
      replaceExisting,
      chunkSize,
      chunkOverlap,
    });

    return res.json({
      ...result,
      extractedChars: text.length,
    });
  } catch (error) {
    return res.status(500).json({
      error: 'Failed to index resume file',
      details: error.message,
    });
  }
});

app.post('/api/resume/rag-match', async (req, res) => {
  try {
    const { query, jobDescription, resumeId, topK, includeFullChunks } = req.body || {};

    if (!query && !jobDescription) {
      return res.status(400).json({
        error: 'query or jobDescription is required',
      });
    }

    const result = await matchResumeWithQuery({
      query,
      jobDescription,
      resumeId,
      topK,
      includeFullChunks:
        includeFullChunks === true ||
        includeFullChunks === 1 ||
        String(includeFullChunks || '').toLowerCase() === 'true',
    });

    return res.json(result);
  } catch (error) {
    return res.status(500).json({
      error: 'Failed to run resume RAG match',
      details: error.message,
    });
  }
});

app.post('/api/resume/full-text', async (req, res) => {
  try {
    const { resumeId } = req.body || {};
    if (!resumeId || !String(resumeId).trim()) {
      return res.status(400).json({ error: 'resumeId is required' });
    }

    const mongoose = require('mongoose');
    const db = mongoose.connection.db;
    if (!db) {
      return res.status(500).json({ error: 'Database connection is not ready' });
    }

    const collectionName = process.env.RESUME_CHUNKS_COLLECTION || 'resume_chunks';
    const docs = await db
      .collection(collectionName)
      .find({ resumeId: String(resumeId).trim() })
      .project({ chunkText: 1, chunkIndex: 1 })
      .sort({ chunkIndex: 1, _id: 1 })
      .toArray();

    if (!docs.length) {
      return res.status(404).json({ error: 'No indexed chunks found for this resumeId' });
    }

    const fullText = docs
      .map((doc) => (doc.chunkText || '').trim())
      .filter(Boolean)
      .join('\n\n');
    const fullTextPlain = fullText
      .replace(/\r/g, '\n')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/\n+/g, ' ')
      .replace(/[ \t]{2,}/g, ' ')
      .trim();

    return res.json({
      resumeId: String(resumeId).trim(),
      chunkCount: docs.length,
      fullText,
      fullTextPlain,
    });
  } catch (error) {
    return res.status(500).json({
      error: 'Failed to fetch resume full text',
      details: error.message,
    });
  }
});
app.use(express.urlencoded({ extended: true }));

// Serve uploaded resumes as static files
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// Health Check Route
app.get('/', (req, res) => {
  res.json({ message: 'PlacementBot AI API is running 🚀' });
});

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/students', studentRoutes);
app.use('/api/jobs', jobRoutes);
app.use('/api/applications', applicationRoutes);
app.post('/api/tasks/log-application', logAutomationApplication);
app.use('/api/match', matchRoutes);

// Error Handling Middleware (must be last)
app.use(errorMiddleware);

const port = PORT || 5000;
server.listen(port, () => {
  console.log(`Server running on http://localhost:${port}`);
});
