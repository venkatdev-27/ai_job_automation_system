const mongoose = require('mongoose');

const DEFAULT_TOP_K = 5;
const DEFAULT_VECTOR_QUERY_RETRIES = 4;
const DEFAULT_VECTOR_QUERY_RETRY_DELAY_MS = 1500;

const STOP_WORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'have', 'in', 'is',
  'it', 'its', 'of', 'on', 'or', 'that', 'the', 'their', 'this', 'to', 'was', 'were', 'with',
  'will', 'can', 'you', 'your', 'we', 'our', 'they', 'them',
]);

function tokenize(text) {
  return (text || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((token) => token.length > 2 && !STOP_WORDS.has(token));
}

function uniqueTokens(tokens) {
  return [...new Set(tokens)];
}

function normalizeVectorScore(score) {
  if (typeof score !== 'number' || Number.isNaN(score)) return 0;
  if (score <= 0) return 0;
  if (score <= 1) return score;
  if (score <= 2) return score / 2;
  return Math.min(score / 10, 1);
}

function getChunkText(chunk) {
  return (
    chunk.chunkText ||
    chunk.text ||
    chunk.content ||
    chunk.pageContent ||
    chunk.body ||
    ''
  ).toString();
}

function normalizeTextForResponse(text, { singleLine = false } = {}) {
  const normalized = (text || "")
    .replace(/\r/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();

  if (singleLine) {
    return normalized.replace(/\n+/g, " ").replace(/[ \t]{2,}/g, " ").trim();
  }

  return normalized;
}

function getResumeId(chunk) {
  return (
    chunk.resumeId ||
    chunk.resume_id ||
    chunk.candidateId ||
    chunk.candidate_id ||
    null
  );
}

function buildFilter(resumeId) {
  if (!resumeId) return null;
  if (mongoose.Types.ObjectId.isValid(resumeId)) {
    return { resumeId: new mongoose.Types.ObjectId(resumeId) };
  }
  return { resumeId: resumeId };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

async function getGeminiQueryEmbedding(queryText) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY is required for EMBEDDING_PROVIDER=gemini');
  }

  const model = process.env.EMBEDDING_MODEL || 'gemini-embedding-001';
  const modelPath = model.startsWith('models/') ? model : `models/${model}`;
  const body = {
    model: modelPath,
    content: {
      parts: [{ text: queryText }],
    },
    taskType: 'RETRIEVAL_QUERY',
  };

  const outputDimensionality = parseEmbeddingDimensions();
  if (outputDimensionality) {
    body.outputDimensionality = outputDimensionality;
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
    throw new Error(`Gemini query embedding failed (${response.status}): ${errorBody}`);
  }

  const payload = await response.json();
  const vector = payload?.embedding?.values;
  if (!Array.isArray(vector) || vector.length === 0) {
    throw new Error('Gemini embedding response was invalid');
  }
  return vector;
}

async function getOpenAIQueryEmbedding(queryText) {
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
      input: queryText,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`OpenAI query embedding failed (${response.status}): ${errorBody}`);
  }

  const payload = await response.json();
  const vector = payload?.data?.[0]?.embedding;
  if (!Array.isArray(vector) || vector.length === 0) {
    throw new Error('OpenAI embedding response was invalid');
  }
  return vector;
}

async function getQueryEmbedding(queryText) {
  const provider = resolveEmbeddingProvider();

  if (provider === 'gemini') {
    return getGeminiQueryEmbedding(queryText);
  }
  if (provider === 'openai') {
    return getOpenAIQueryEmbedding(queryText);
  }

  throw new Error(
    'No embedding provider configured. Set EMBEDDING_PROVIDER to "gemini" or "openai" and provide the matching API key.'
  );
}

async function retrieveChunksByVector(embedding, { topK = DEFAULT_TOP_K, resumeId } = {}) {
  const db = mongoose.connection.db;
  if (!db) {
    throw new Error('Database connection is not ready');
  }

  const collectionName = process.env.RESUME_CHUNKS_COLLECTION || 'resume_chunks';
  const indexName = process.env.VECTOR_INDEX_NAME || 'resume_chunks_vector_index';
  const embeddingField = process.env.VECTOR_EMBEDDING_FIELD || 'embedding';
  const limit = Math.max(1, Math.min(Number(topK) || DEFAULT_TOP_K, 20));
  const numCandidates = Math.max(limit * 20, 50);

  const vectorStage = {
    $vectorSearch: {
      index: indexName,
      path: embeddingField,
      queryVector: embedding,
      numCandidates,
      limit,
    },
  };

  const filter = buildFilter(resumeId);
  if (filter) {
    vectorStage.$vectorSearch.filter = filter;
  }

  const pipeline = [
    vectorStage,
    {
      $project: {
        _id: 1,
        resumeId: 1,
        resume_id: 1,
        candidateId: 1,
        candidate_id: 1,
        chunkText: 1,
        text: 1,
        content: 1,
        pageContent: 1,
        body: 1,
        score: { $meta: 'vectorSearchScore' },
      },
    },
  ];

  const docs = await db.collection(collectionName).aggregate(pipeline).toArray();
  return docs.map((doc) => ({
    id: doc._id,
    resumeId: getResumeId(doc),
    text: getChunkText(doc).trim(),
    vectorScoreRaw: doc.score,
    vectorScore: normalizeVectorScore(doc.score),
  })).filter((chunk) => chunk.text.length > 0);
}

async function retrieveChunksByVectorWithRetry(embedding, { topK = DEFAULT_TOP_K, resumeId } = {}) {
  const retries = Math.max(1, Number(process.env.VECTOR_QUERY_RETRIES || DEFAULT_VECTOR_QUERY_RETRIES));
  const delayMs = Math.max(100, Number(process.env.VECTOR_QUERY_RETRY_DELAY_MS || DEFAULT_VECTOR_QUERY_RETRY_DELAY_MS));

  for (let attempt = 1; attempt <= retries; attempt += 1) {
    const chunks = await retrieveChunksByVector(embedding, { topK, resumeId });
    if (chunks.length > 0) {
      return chunks;
    }

    if (attempt < retries) {
      await sleep(delayMs);
    }
  }

  return [];
}

function sentenceScore(sentence, queryTokens) {
  if (!sentence) return 0;
  const lower = sentence.toLowerCase();
  let matches = 0;
  for (const token of queryTokens) {
    if (lower.includes(token)) matches += 1;
  }
  return matches;
}

function getTopEvidence(chunks, queryTokens, maxItems = 3) {
  const sentences = [];

  for (const chunk of chunks) {
    const split = chunk.text
      .replace(/\s+/g, ' ')
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter(Boolean);

    for (const sentence of split) {
      const hitCount = sentenceScore(sentence, queryTokens);
      if (hitCount > 0) {
        sentences.push({
          sentence: sentence.length > 240 ? `${sentence.slice(0, 237)}...` : sentence,
          hitCount,
          vectorScore: chunk.vectorScore,
        });
      }
    }
  }

  sentences.sort((a, b) => (b.hitCount - a.hitCount) || (b.vectorScore - a.vectorScore));
  return sentences.slice(0, maxItems).map((item) => item.sentence);
}

function buildAssessment(queryText, chunks) {
  const queryTokens = uniqueTokens(tokenize(queryText));
  const context = chunks.map((chunk) => chunk.text).join(' ');
  const contextLower = context.toLowerCase();

  const matchedTokens = queryTokens.filter((token) => contextLower.includes(token));
  const tokenCoverage = queryTokens.length ? matchedTokens.length / queryTokens.length : 0;

  const avgVectorScore = chunks.length
    ? chunks.reduce((sum, chunk) => sum + chunk.vectorScore, 0) / chunks.length
    : 0;

  const finalScore = Math.round(((avgVectorScore * 0.7) + (tokenCoverage * 0.3)) * 100);

  let verdict = 'Weak match';
  if (finalScore >= 80) verdict = 'Strong match';
  else if (finalScore >= 60) verdict = 'Moderate match';

  const evidence = getTopEvidence(chunks, queryTokens, 3);
  const matchedPreview = matchedTokens.slice(0, 12);

  const reasoning = [
    `Retrieved ${chunks.length} relevant chunk(s) from vector search.`,
    `Average vector relevance: ${(avgVectorScore * 100).toFixed(1)}%.`,
    `Query term coverage in retrieved context: ${(tokenCoverage * 100).toFixed(1)}%.`,
    matchedPreview.length ? `Matched terms: ${matchedPreview.join(', ')}.` : 'No direct query terms were found in retrieved chunks.',
  ].join(' ');

  const answer = `${verdict}. Score ${finalScore}/100 based only on retrieved resume chunks.`;

  return {
    answer,
    score: finalScore,
    verdict,
    reasoning,
    evidence,
  };
}

async function matchResumeWithQuery({ query, jobDescription, resumeId, topK, includeFullChunks = false } = {}) {
  const queryText = (query || jobDescription || '').trim();
  if (!queryText) {
    throw new Error('query or jobDescription is required');
  }

  const embedding = await getQueryEmbedding(queryText);
  const chunks = await retrieveChunksByVectorWithRetry(embedding, { topK, resumeId });

  if (!chunks.length) {
    return {
      answer: 'No relevant resume context found in vector database.',
      score: 0,
      verdict: 'No match data',
      reasoning: 'Vector retrieval returned zero chunks, so no context-only assessment could be made.',
      evidence: [],
      retrievedChunks: [],
    };
  }

  const assessment = buildAssessment(queryText, chunks);
  return {
    ...assessment,
    retrievedChunks: chunks.map((chunk) => ({
      id: chunk.id,
      resumeId: chunk.resumeId,
      vectorScore: Number(chunk.vectorScore.toFixed(4)),
      text: includeFullChunks
        ? normalizeTextForResponse(chunk.text)
        : normalizeTextForResponse(
          chunk.text.length > 500 ? `${chunk.text.slice(0, 497)}...` : chunk.text,
          { singleLine: true }
        ),
    })),
  };
}

module.exports = {
  matchResumeWithQuery,
};
