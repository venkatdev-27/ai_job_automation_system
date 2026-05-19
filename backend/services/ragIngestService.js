const mongoose = require('mongoose');

const DEFAULT_CHUNK_SIZE = 900;
const DEFAULT_CHUNK_OVERLAP = 150;

function splitIntoChunks(text, chunkSize = DEFAULT_CHUNK_SIZE, overlap = DEFAULT_CHUNK_OVERLAP) {
  const cleaned = (text || '')
    .replace(/\r/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
  if (!cleaned) return [];

  const chunks = [];
  let start = 0;

  while (start < cleaned.length) {
    let end = Math.min(start + chunkSize, cleaned.length);

    // Prefer to break near sentence/line boundaries for better semantic chunks.
    if (end < cleaned.length) {
      const boundarySlice = cleaned.slice(start, end + 120);
      const breakMatch = boundarySlice.match(/[\n\.!?](?!.*[\n\.!?])/);
      if (breakMatch) {
        end = start + breakMatch.index + 1;
      }
    }

    const chunk = cleaned.slice(start, end).trim();
    if (chunk) chunks.push(chunk);

    if (end >= cleaned.length) break;
    start = Math.max(end - overlap, start + 1);
  }

  return chunks;
}

function resolveEmbeddingProvider() {
  if (process.env.EMBEDDING_PROVIDER) {
    return process.env.EMBEDDING_PROVIDER.toLowerCase();
  }
  if (process.env.GEMINI_API_KEY) return 'gemini';
  if (process.env.OPENAI_API_KEY) return 'openai';
  return 'unknown';
}

function parseEmbeddingDimensions() {
  const raw = process.env.EMBEDDING_DIMENSIONS;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) return undefined;
  return Math.floor(value);
}

async function getGeminiEmbedding(inputText, taskType = 'RETRIEVAL_DOCUMENT', title) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY is required for EMBEDDING_PROVIDER=gemini');
  }

  const model = process.env.EMBEDDING_MODEL || 'gemini-embedding-001';
  const modelPath = model.startsWith('models/') ? model : `models/${model}`;

  const body = {
    model: modelPath,
    content: {
      parts: [{ text: inputText }],
    },
    taskType,
  };

  const outputDimensionality = parseEmbeddingDimensions();
  if (outputDimensionality) {
    body.outputDimensionality = outputDimensionality;
  }
  if (title && taskType === 'RETRIEVAL_DOCUMENT') {
    body.title = title;
  }

  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/${modelPath}:embedContent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-goog-api-key': apiKey,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Gemini embedding failed (${response.status}): ${errorBody}`);
  }

  const payload = await response.json();
  const embedding = payload?.embedding?.values;
  if (!Array.isArray(embedding) || embedding.length === 0) {
    throw new Error('Gemini embedding response was invalid');
  }
  return embedding;
}

async function getOpenAIEmbedding(inputText) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY is required for EMBEDDING_PROVIDER=openai');
  }

  const model = process.env.EMBEDDING_MODEL || 'text-embedding-3-small';
  const response = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      input: inputText,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`OpenAI embedding failed (${response.status}): ${errorBody}`);
  }

  const payload = await response.json();
  const embedding = payload?.data?.[0]?.embedding;
  if (!Array.isArray(embedding) || embedding.length === 0) {
    throw new Error('OpenAI embedding response was invalid');
  }
  return embedding;
}

async function getEmbedding(inputText, options = {}) {
  const provider = resolveEmbeddingProvider();

  if (provider === 'gemini') {
    return getGeminiEmbedding(inputText, options.taskType, options.title);
  }
  if (provider === 'openai') {
    return getOpenAIEmbedding(inputText);
  }

  throw new Error(
    'No embedding provider configured. Set EMBEDDING_PROVIDER to "gemini" or "openai" and provide the matching API key.'
  );
}

async function ingestResumeTextToVectorDb({
  resumeId,
  text,
  sourceName,
  replaceExisting = true,
  chunkSize = DEFAULT_CHUNK_SIZE,
  chunkOverlap = DEFAULT_CHUNK_OVERLAP,
} = {}) {
  const cleanText = (text || '').trim();
  if (!cleanText) throw new Error('text is required');

  const db = mongoose.connection.db;
  if (!db) throw new Error('Database connection is not ready');

  const resolvedResumeId = (resumeId || new mongoose.Types.ObjectId().toString()).toString();
  const chunks = splitIntoChunks(cleanText, Number(chunkSize), Number(chunkOverlap));
  if (!chunks.length) throw new Error('No chunks generated from input text');

  const collectionName = process.env.RESUME_CHUNKS_COLLECTION || 'resume_chunks';
  const collection = db.collection(collectionName);

  if (replaceExisting) {
    await collection.deleteMany({ resumeId: resolvedResumeId });
  }

  const docs = [];
  for (let i = 0; i < chunks.length; i += 1) {
    const chunkText = chunks[i];
    const embedding = await getEmbedding(chunkText, {
      taskType: 'RETRIEVAL_DOCUMENT',
      title: sourceName || resolvedResumeId,
    });
    docs.push({
      resumeId: resolvedResumeId,
      chunkIndex: i,
      chunkText,
      embedding,
      sourceName: sourceName || null,
      createdAt: new Date(),
      updatedAt: new Date(),
    });
  }

  const insertResult = await collection.insertMany(docs);

  return {
    resumeId: resolvedResumeId,
    chunkCount: docs.length,
    insertedCount: insertResult.insertedCount || Object.keys(insertResult.insertedIds || {}).length,
    embeddingDimensions: docs[0]?.embedding?.length || 0,
  };
}

module.exports = {
  ingestResumeTextToVectorDb,
  splitIntoChunks,
};
