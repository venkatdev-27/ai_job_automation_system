const fs = require("fs/promises");
const path = require("path");
const { execFile } = require("child_process");
const { promisify } = require("util");
const mammoth = require("mammoth");

const execFileAsync = promisify(execFile);

function getExtension(filePath, originalName = "") {
  const source = originalName || filePath || "";
  return path.extname(source).toLowerCase();
}

function resolvePythonBin() {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN;
  return process.platform === "win32" ? "python" : "python3";
}

function resolveSofficeBin() {
  if (process.env.SOFFICE_BIN) return process.env.SOFFICE_BIN;
  return "soffice";
}

function normalizeExtractedText(text) {
  return (text || "")
    .replace(/\r/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

async function extractPdfWithPyMuPDF(filePath) {
  const scriptPath = path.resolve(__dirname, "../scripts/extract_pdf.py");
  const { stdout, stderr } = await execFileAsync(resolvePythonBin(), [scriptPath, filePath], {
    maxBuffer: 20 * 1024 * 1024,
  });

  if (stderr && stderr.trim()) {
    throw new Error(stderr.trim());
  }

  return normalizeExtractedText(stdout || "");
}

async function extractDocxWithMammoth(filePath) {
  const result = await mammoth.extractRawText({ path: filePath });
  return normalizeExtractedText(result.value || "");
}

async function convertDocToDocx(docPath) {
  const outputDir = path.dirname(docPath);
  const sofficeBin = resolveSofficeBin();

  await execFileAsync(sofficeBin, [
    "--headless",
    "--convert-to",
    "docx",
    docPath,
    "--outdir",
    outputDir,
  ]);

  const docxPath = path.join(outputDir, `${path.parse(docPath).name}.docx`);
  await fs.access(docxPath);
  return docxPath;
}

async function extractResumeText(filePath, originalName = "") {
  const ext = getExtension(filePath, originalName);

  if (ext === ".pdf") {
    return extractPdfWithPyMuPDF(filePath);
  }

  if (ext === ".docx") {
    return extractDocxWithMammoth(filePath);
  }

  if (ext === ".doc") {
    const convertedDocxPath = await convertDocToDocx(filePath);
    const text = await extractDocxWithMammoth(convertedDocxPath);

    if (convertedDocxPath !== filePath) {
      await fs.unlink(convertedDocxPath).catch(() => {});
    }

    return text;
  }

  throw new Error(`Unsupported file type: ${ext || "unknown"}`);
}

module.exports = {
  extractResumeText,
  extractPdfWithPyMuPDF,
  extractDocxWithMammoth,
  convertDocToDocx,
  normalizeExtractedText,
};
