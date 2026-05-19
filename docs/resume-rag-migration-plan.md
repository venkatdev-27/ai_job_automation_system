# Resume + RAG Migration Plan

## Goal
Move from only "normal MongoDB storage" to a production-ready flow:
- Store resume files in Cloudinary.
- Parse resume text from `.pdf`, `.docx`, `.doc`.
- Create embeddings and store vectors for semantic search.
- Use RAG to answer resume-understanding questions and improve job-platform automation quality.

## Recommended Stack
- Primary DB: MongoDB Atlas (keep existing `ai_bot_resumes` database).
- Vector layer: MongoDB Atlas Vector Search (recommended first because your data is already in Atlas).
- File storage: Cloudinary (`resource_type: raw` for resumes).
- Embeddings: OpenAI `text-embedding-3-small` (1536 dims) or `text-embedding-3-large` (3072 dims).
- LLM for RAG answers: your current model provider (or OpenAI chat model).

## High-Level Flow
1. User submits profile + uploads resume.
2. Backend uploads original file to Cloudinary and stores metadata in MongoDB.
3. Backend extracts text (`pdf/docx/doc`) using parser service.
4. Backend chunks extracted text (token-aware chunking + overlap).
5. Backend generates embeddings for each chunk.
6. Backend stores chunks + vectors in `resume_chunks`.
7. For any resume query, backend:
   - embeds user query,
   - runs vector search,
   - builds context from top chunks,
   - calls LLM with RAG prompt,
   - returns grounded answer.

## Data Model Changes

### `resumes` collection
Suggested document shape:

```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "originalFilename": "john_resume.docx",
  "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "cloudinary": {
    "publicId": "ai_bot_resumes/user_123/resume_20260402_101010",
    "secureUrl": "https://res.cloudinary.com/.../raw/upload/...",
    "bytes": 154221,
    "version": 1712020202
  },
  "textExtractStatus": "completed",
  "textLength": 18452,
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

### `resume_chunks` collection
Suggested document shape:

```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "resumeId": "ObjectId",
  "chunkIndex": 0,
  "chunkText": "Senior Backend Engineer with 6+ years...",
  "embedding": [0.0123, -0.044, 0.009, "..."],
  "sourceMeta": {
    "page": 1,
    "section": "experience"
  },
  "createdAt": "ISODate"
}
```

## MongoDB Atlas Vector Index
Create vector index on `resume_chunks.embedding`:
- Path: `embedding`
- Dimensions: `1536` if `text-embedding-3-small` is used
- Similarity: `cosine`

Optional secondary indexes:
- `{ userId: 1, resumeId: 1 }`
- `{ userId: 1, createdAt: -1 }`

## Cloudinary Storage Plan
- Upload with `resource_type: "raw"` to avoid image transforms.
- Folder strategy: `ai_bot_resumes/{userId}/`.
- Save `public_id` and `secure_url` in `resumes`.
- Keep only metadata in MongoDB, not file binary.

## RAG Query Pattern
1. Generate query embedding.
2. Run `$vectorSearch` with filter `{ userId }` (and optionally `resumeId`).
3. Retrieve top `k=5..10` chunks.
4. Build grounded prompt:
   - system: "Answer only from context."
   - context: concatenated chunks
   - question: user query
5. Return answer + supporting chunk references.

## Security and Credentials (Important)
You mentioned storing credentials (Naukri, LinkedIn, Indeed, Internshala).

Do not store these as plaintext.
Use:
- encryption at rest (field-level encryption or app-level AES-256-GCM),
- secret key in env/KMS,
- strict access controls and audit logs.

Minimum fields:
- `platform`
- `username` (masked where possible)
- `encryptedPassword`
- `iv`
- `authTag`
- `lastUpdatedAt`

## Rollout Plan
1. Add Cloudinary upload path and `resumes` metadata updates.
2. Run parser + chunk + embedding pipeline async after upload.
3. Add `resume_chunks` collection + Atlas vector index.
4. Add `/resume/rag/query` API endpoint.
5. Backfill embeddings for old resumes via background job.
6. Add monitoring:
   - extraction success rate,
   - chunk count per resume,
   - vector search latency,
   - RAG answer quality checks.

## Immediate Next Implementation Tasks
1. Wire Cloudinary upload into current resume upload API.
2. Add an async worker/service: `extract -> chunk -> embed -> store`.
3. Add vector retrieval service and one RAG endpoint.
4. Encrypt job-platform credentials before DB write.

---
Assumption used in this plan: your backend is Node.js with MongoDB Atlas already in use, and resume extraction currently relies on `backend/scripts/extract_pdf.py`.
