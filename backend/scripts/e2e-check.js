/* eslint-disable no-console */
require('dotenv').config();

const fs = require('fs');
const path = require('path');
const os = require('os');
const mongoose = require('mongoose');
const { v2: cloudinary } = require('cloudinary');

const BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000';
const COLLECTION = process.env.RESUME_CHUNKS_COLLECTION || 'resume_chunks';
const VECTOR_INDEX_NAME = process.env.VECTOR_INDEX_NAME || 'resume_chunks_vector_index';
const EMBEDDING_FIELD = process.env.VECTOR_EMBEDDING_FIELD || 'embedding';

const fileArgIndex = process.argv.findIndex((arg) => arg === '--file');
const resumeFilePath = fileArgIndex >= 0 ? process.argv[fileArgIndex + 1] : '';

function nowTag() {
  return new Date().toISOString().replace(/[-:.TZ]/g, '');
}

function pass(label, details = '') {
  console.log(`PASS  ${label}${details ? ` - ${details}` : ''}`);
}

function fail(label, details = '') {
  console.log(`FAIL  ${label}${details ? ` - ${details}` : ''}`);
}

async function checkCloudinary() {
  cloudinary.config({
    cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
    api_key: process.env.CLOUDINARY_API_KEY,
    api_secret: process.env.CLOUDINARY_API_SECRET,
  });

  const ping = await cloudinary.api.ping();
  if (ping?.status !== 'ok') {
    throw new Error(`Unexpected ping result: ${JSON.stringify(ping)}`);
  }
}

async function checkMongoAndVectorIndex() {
  if (!process.env.MONGO_URI) {
    throw new Error('MONGO_URI is missing');
  }

  await mongoose.connect(process.env.MONGO_URI);
  const db = mongoose.connection.db;
  if (!db) throw new Error('Mongo connection is not ready');

  const indexes = await db.collection(COLLECTION).aggregate([{ $listSearchIndexes: {} }]).toArray();
  const vectorIndex = indexes.find((idx) => idx.name === VECTOR_INDEX_NAME);
  if (!vectorIndex) {
    throw new Error(`Vector index not found: ${VECTOR_INDEX_NAME}`);
  }
  if (!vectorIndex.queryable) {
    throw new Error(`Vector index is not queryable yet: ${VECTOR_INDEX_NAME}`);
  }
}

async function checkGeminiLlm() {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new Error('GEMINI_API_KEY is missing');

  const model = process.env.GEMINI_MODEL || 'gemini-2.0-flash';
  const modelPath = model.startsWith('models/') ? model : `models/${model}`;
  const resp = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/${modelPath}:generateContent`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-goog-api-key': key,
      },
      body: JSON.stringify({
        contents: [{ parts: [{ text: 'Reply with exactly: OK' }] }],
      }),
    }
  );

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Gemini call failed (${resp.status}): ${body}`);
  }

  const data = await resp.json();
  const text = data?.candidates?.[0]?.content?.parts?.map((p) => p.text || '').join(' ').trim();
  if (!text) {
    throw new Error('Gemini response had no text');
  }
}

function resolveResumeFile() {
  if (resumeFilePath && fs.existsSync(resumeFilePath)) {
    return resumeFilePath;
  }

  const fallbacks = [
    path.resolve(process.cwd(), 'uploads', 'resume.pdf'),
    path.resolve(process.cwd(), 'uploads', 'resume.docx'),
    path.resolve(process.cwd(), 'uploads', 'resume.doc'),
  ];
  for (const candidate of fallbacks) {
    if (fs.existsSync(candidate)) return candidate;
  }

  return '';
}

async function callUploadAndIndex(filePath, resumeId) {
  const bytes = await fs.promises.readFile(filePath);
  const form = new FormData();
  form.append('resume', new Blob([bytes]), path.basename(filePath));
  form.append('resumeId', resumeId);
  form.append('replaceExisting', 'true');

  const resp = await fetch(`${BASE_URL}/api/resume/upload-and-index`, {
    method: 'POST',
    body: form,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(`upload-and-index failed (${resp.status}): ${JSON.stringify(data)}`);
  }
  return data;
}

async function callRagMatch(resumeId) {
  const resp = await fetch(`${BASE_URL}/api/resume/rag-match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      resumeId,
      query: 'Match this resume for backend role with Node.js, APIs, and database work.',
    }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(`rag-match failed (${resp.status}): ${JSON.stringify(data)}`);
  }
  return data;
}

async function callRagMatchWithRetry(resumeId) {
  const retries = Math.max(1, Number(process.env.VECTOR_QUERY_RETRIES || 4));
  const delayMs = Math.max(100, Number(process.env.VECTOR_QUERY_RETRY_DELAY_MS || 1500));

  for (let attempt = 1; attempt <= retries; attempt += 1) {
    const rag = await callRagMatch(resumeId);
    const retrieved = Array.isArray(rag?.retrievedChunks) ? rag.retrievedChunks.length : 0;
    if (retrieved > 0) return rag;

    if (attempt < retries) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  return callRagMatch(resumeId);
}

async function checkVectorDataForResume(resumeId) {
  const db = mongoose.connection.db;
  const count = await db.collection(COLLECTION).countDocuments({
    resumeId,
    [EMBEDDING_FIELD]: { $exists: true, $type: 'array' },
  });
  return count;
}

async function main() {
  const results = [];
  const resumeId = `e2e_${nowTag()}`;
  const filePath = resolveResumeFile();

  try {
    await checkCloudinary();
    results.push({ ok: true, label: 'Cloudinary ping' });
    pass('Cloudinary ping');
  } catch (err) {
    results.push({ ok: false, label: 'Cloudinary ping', err: err.message });
    fail('Cloudinary ping', err.message);
  }

  try {
    await checkMongoAndVectorIndex();
    results.push({ ok: true, label: 'Mongo + Vector index' });
    pass('Mongo + Vector index', `${COLLECTION}/${VECTOR_INDEX_NAME}`);
  } catch (err) {
    results.push({ ok: false, label: 'Mongo + Vector index', err: err.message });
    fail('Mongo + Vector index', err.message);
  }

  try {
    await checkGeminiLlm();
    results.push({ ok: true, label: 'Gemini LLM call' });
    pass('Gemini LLM call');
  } catch (err) {
    results.push({ ok: false, label: 'Gemini LLM call', err: err.message });
    fail('Gemini LLM call', err.message);
  }

  if (!filePath) {
    results.push({
      ok: false,
      label: 'Upload + Index + RAG',
      err: 'No local resume file found. Pass --file <path>.',
    });
    fail('Upload + Index + RAG', 'No local resume file found. Pass --file <path>.');
  } else {
    try {
      const up = await callUploadAndIndex(filePath, resumeId);
      pass('Upload + Index endpoint', `chunks=${up?.indexing?.chunkCount ?? 'n/a'}`);

      const count = await checkVectorDataForResume(resumeId);
      if (count <= 0) {
        throw new Error('No vectors found in Mongo after indexing');
      }
      pass('Vector write', `documents=${count}`);

      const rag = await callRagMatchWithRetry(resumeId);
      const retrieved = Array.isArray(rag?.retrievedChunks) ? rag.retrievedChunks.length : 0;
      if (retrieved <= 0) {
        throw new Error(`RAG returned no retrievedChunks: ${JSON.stringify(rag)}`);
      }
      pass('RAG retrieval + scoring', `retrievedChunks=${retrieved}, score=${rag?.score ?? 'n/a'}`);
      results.push({ ok: true, label: 'Upload + Index + RAG' });
    } catch (err) {
      results.push({ ok: false, label: 'Upload + Index + RAG', err: err.message });
      fail('Upload + Index + RAG', err.message);
    }
  }

  const failed = results.filter((r) => !r.ok);
  if (failed.length) {
    console.log('\nE2E RESULT: FAILED');
    for (const f of failed) {
      console.log(`- ${f.label}: ${f.err}`);
    }
    process.exitCode = 1;
  } else {
    console.log('\nE2E RESULT: PASSED');
  }
}

main()
  .catch((err) => {
    console.error('Unhandled error:', err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await mongoose.disconnect().catch(() => {});
  });
