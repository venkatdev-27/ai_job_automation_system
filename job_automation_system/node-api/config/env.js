require('dotenv').config();

const provider =
  process.env.EMBEDDING_PROVIDER ||
  (process.env.GEMINI_API_KEY ? 'gemini' : 'openai');

module.exports = {
  PYTHON_BIN: process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3'),
  SOFFICE_BIN: process.env.SOFFICE_BIN || 'soffice',
  GEMINI_API_KEY: process.env.GEMINI_API_KEY,
  OPENAI_API_KEY: process.env.OPENAI_API_KEY,

  EMBEDDING_PROVIDER: provider,
  EMBEDDING_MODEL:
    process.env.EMBEDDING_MODEL ||
    (provider === 'gemini' ? 'gemini-embedding-001' : 'text-embedding-3-small'),

  EMBEDDING_DIMENSIONS: Number(process.env.EMBEDDING_DIMENSIONS || 0) || undefined,
  RESUME_CHUNKS_COLLECTION: process.env.RESUME_CHUNKS_COLLECTION || 'resume_chunks',
  VECTOR_INDEX_NAME: process.env.VECTOR_INDEX_NAME || 'resume_chunks_vector_index',
  VECTOR_EMBEDDING_FIELD: process.env.VECTOR_EMBEDDING_FIELD || 'embedding',

  PORT: process.env.PORT,
  MONGO_URI: process.env.MONGO_URI,
  JWT_SECRET: process.env.JWT_SECRET,
  NODE_ENV: process.env.NODE_ENV || 'development',
};
