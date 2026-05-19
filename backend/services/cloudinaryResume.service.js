const path = require("path");
const { getCloudinary } = require("../config/cloudinary");

const RESUME_ROOT_FOLDER = "ai_bot_resumes";

function sanitizeSegment(value) {
  return String(value || "unknown")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function buildResumePublicId({ userId, originalFilename }) {
  const baseName = path.parse(originalFilename || "resume").name || "resume";
  const safeBaseName = sanitizeSegment(baseName) || "resume";
  const ts = new Date().toISOString().replace(/[-:.TZ]/g, "");
  return `${safeBaseName}_${ts}`;
}

function buildFolder(userId) {
  return `${RESUME_ROOT_FOLDER}/${sanitizeSegment(userId)}`;
}

function normalizeUploadResult(result, originalFilename, mimeType) {
  return {
    publicId: result.public_id,
    secureUrl: result.secure_url,
    bytes: result.bytes,
    version: result.version,
    resourceType: result.resource_type,
    format: result.format || null,
    originalFilename: originalFilename || null,
    mimeType: mimeType || null,
  };
}

async function uploadResumeFromPath({
  filePath,
  userId,
  originalFilename,
  mimeType,
}) {
  if (!filePath) throw new Error("filePath is required.");
  if (!userId) throw new Error("userId is required.");

  const cloudinary = getCloudinary();
  const publicId = buildResumePublicId({ userId, originalFilename });
  const folder = buildFolder(userId);

  const result = await cloudinary.uploader.upload(filePath, {
    resource_type: "raw",
    folder,
    public_id: publicId,
    overwrite: true,
    unique_filename: false,
    use_filename: false,
  });

  return normalizeUploadResult(result, originalFilename, mimeType);
}

function uploadResumeFromBuffer({ buffer, userId, originalFilename, mimeType }) {
  if (!Buffer.isBuffer(buffer)) throw new Error("buffer must be a Buffer.");
  if (!userId) throw new Error("userId is required.");

  const cloudinary = getCloudinary();
  const publicId = buildResumePublicId({ userId, originalFilename });
  const folder = buildFolder(userId);

  return new Promise((resolve, reject) => {
    const stream = cloudinary.uploader.upload_stream(
      {
        resource_type: "raw",
        folder,
        public_id: publicId,
        overwrite: true,
        unique_filename: false,
        use_filename: false,
      },
      (error, result) => {
        if (error) return reject(error);
        return resolve(normalizeUploadResult(result, originalFilename, mimeType));
      }
    );

    stream.end(buffer);
  });
}

async function deleteResumeAsset(publicId) {
  if (!publicId) throw new Error("publicId is required.");
  const cloudinary = getCloudinary();
  return cloudinary.uploader.destroy(publicId, { resource_type: "raw" });
}

module.exports = {
  uploadResumeFromPath,
  uploadResumeFromBuffer,
  deleteResumeAsset,
};
