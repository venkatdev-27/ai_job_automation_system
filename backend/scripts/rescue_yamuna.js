const https = require('https');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });
const { extractResumeText } = require('../services/resumeTextExtractor');
const resumeBuilderService = require('../services/resumeBuilderService');

// Refactored helper to download using native https
function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https.get(url, (response) => {
      if (response.statusCode !== 200) {
        return reject(new Error(`Failed to download file: ${response.statusCode}`));
      }
      response.pipe(file);
      file.on('finish', () => {
        file.close(resolve);
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
}

async function rescue() {
  const url = 'https://res.cloudinary.com/dco7jegub/raw/upload/ai_bot_resumes/resume_1775310384519_mani.docx';
  const localPath = path.resolve(__dirname, 'temp_mani.docx');

  console.log('🚀 Downloading resume from Cloudinary (using native https)...');
  
  try {
    await downloadFile(url, localPath);
    console.log('✅ Download complete. Extracting text...');

    // Try docx extraction (uses mammoth)
    let text = "";
    try {
      text = await extractResumeText(localPath, 'mani.docx');
    } catch (e) {
      console.log('⚠️ DOCX extraction failed. Trying PDF extraction as fallback...');
      // Mislabeled PDF check
      const { extractPdfWithPyMuPDF } = require('../services/resumeTextExtractor');
      text = await extractPdfWithPyMuPDF(localPath);
    }

    if (!text || text.trim().length < 50) {
      console.error('❌ ERROR: No text could be extracted from the file. Length:', text?.length);
      process.exit(1);
    }

    console.log('✅ Extraction SUCCESS! Length:', text.length);
    console.log('--- CONTENT PREVIEW ---');
    console.log(text.substring(0, 500).replace(/\n/g, ' '));

    console.log('\n🤖 PHASE: Multi-Agent CrewAI (AI and ML Engineer tailoring for Peddi Yamuna)...');
    
    const jobDescription = "Data Scientist - Python, SQL, Machine Learning, Statistical Analysis, and Data Visualization.";
    
    // Call the verified resume builder service (v13 bot)
    const result = await resumeBuilderService.buildTailoredResume(jobDescription, text);

    console.log('\n✅ SUCCESS: DATA SCIENTIST RESUME GENERATED!');
    console.log(`- Score: ${result.score}`);
    console.log(`- Decision: ${result.decision}`);
    console.log('\n--- TAILORED RESUME ---');
    console.log(result.resumeText);

    // Save to dedicated file for the user
    const finalFile = path.resolve(__dirname, 'YAMUNA_DATA_SCIENTIST_RESUME.md');
    fs.writeFileSync(finalFile, result.resumeText, 'utf8');
    // Generate the Latest PDF with Resilient Naming
    const pdfService = require('../services/pdfService');
    const timestamp = new Date().getTime();
    let finalPDF = path.resolve(__dirname, 'YAMUNA_RESUME_DATA_SCIENTIST.pdf');
    
    console.log(`📄 Generating Latest PDF (v34 Style)...`);
    try {
      await pdfService.generatePDFFromHTML(result.resumeText, finalPDF);
    } catch (e) {
      console.log(`⚠️ Primary PDF locked (EBUSY). Saving to fallback path...`);
      finalPDF = path.resolve(__dirname, `YAMUNA_RESUME_AI_ML_v34_${timestamp}.pdf`);
      await pdfService.generatePDFFromHTML(result.resumeText, finalPDF);
    }
    console.log(`✅ LATEST PDF SAVED TO: ${finalPDF}`);
  } catch (error) {
    console.error('❌ ERROR in rescue process:', error);
  } finally {
    if (fs.existsSync(localPath)) fs.unlinkSync(localPath);
    process.exit(0);
  }
}

rescue();
