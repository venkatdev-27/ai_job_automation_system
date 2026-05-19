const { execFile } = require('child_process');
const path = require('path');
const { extractResumeText } = require('./resumeTextExtractor');

const { GoogleGenerativeAI } = require('@google/generative-ai');

/**
 * Executes the Python script to extract raw text from a PDF securely using PyMuPDF.
 * @param {string} pdfPath - Absolute or relative path to the PDF file.
 */
const extractTextPyMuPDF = (pdfPath) => {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, '../scripts/extract_pdf.py');
    const pythonProcess = execFile('python', [pythonScript, pdfPath], (error, stdout, stderr) => {
      if (error) {
        return reject(new Error(`Native Python extraction failed: ${error.message}`));
      }
      try {
        const response = JSON.parse(stdout);
        if (response.success && response.text) {
          resolve(response.text);
        } else {
          reject(new Error(response.error || "Failed to extract text cleanly."));
        }
      } catch (err) {
        reject(new Error(`Failed to parse Python response securely: ${stdout}`));
      }
    });
  });
};

exports.parseResumeToJSON = async (pdfPath) => {
  try {
    // Phase 1: Multi-format Native Extractions (PDF, DOCX, DOC)
    const rawText = await extractResumeText(pdfPath);

    // Phase 2: Structural JSON translation using Google GenAI
    // Ensure you have `GEMINI_API_KEY` mapped inside your `.env` to operate natively!
    if (!process.env.GEMINI_API_KEY) {
      console.warn("⚠️ GEMINI_API_KEY not found in .env, returning raw text dump as fallback structured payload.");
      return { fallback_raw_text: rawText };
    }

    const ai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
    
    // We force Google schema validation directly in our prompt logic.
    const prompt = `
      You are an expert ATS (Applicant Tracking System) JSON parser.
      Extract the following raw resume payload strictly into this rigid JSON structure (and do not output any markdown or comments, just pure JSON):
      {
        "name": "Full Name",
        "email": "Email Address",
        "phone": "Phone Number",
        "education": [{"degree": "", "institution": "", "year": ""}],
        "experience": [{"role": "", "company": "", "duration": "", "summary": ""}],
        "skills": ["skill1", "skill2"]
      }

      RAW RESUME TEXT:
      ${rawText}
    `;

    const model = ai.getGenerativeModel({
      model: 'gemini-2.5-flash',
      generationConfig: {
        responseMimeType: "application/json",
      }
    });
    
    const result = await model.generateContent(prompt);
    const aiText = result.response.text();
    
    // Clean up typical LLM markdown blocks (e.g. ```json \n {...} \n ```)
    const cleanlyParsed = aiText.replace(/```json/g, '').replace(/```/g, '').trim();

    return JSON.parse(cleanlyParsed);

  } catch (error) {
    console.error("❌ resumeService.parseResumeToJSON Error:", error.message);
    throw error;
  }
};
