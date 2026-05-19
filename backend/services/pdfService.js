const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

/**
 * Professional PDF Generation Service (v27)
 * Converts Elite HTML resumes into high-fidelity A4 PDFs using Puppeteer.
 */
class PDFService {
  /**
   * Generates a PDF from HTML content.
   * @param {string} htmlContent - The raw HTML string with inline CSS.
   * @param {string} outputPath - The full target path for the .pdf file.
   * @returns {Promise<string>} - The path to the generated PDF.
   */
  async generatePDFFromHTML(htmlContent, outputPath) {
    let browser;
    try {
      console.log(`LOG: Launching Puppeteer for PDF generation...`);
      
      // Launch headless Chrome
      browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      });

      const page = await browser.newPage();

      // Set content and wait for network to be idle (ensures styles load)
      await page.setContent(htmlContent, { waitUntil: 'networkidle0' });

      // Generate the A4 PDF
      // We use 0px margins because margins are already defined in the HTML/CSS template (20px).
      await page.pdf({
        path: outputPath,
        format: 'A4',
        printBackground: true,
        margin: {
          top: '0px',
          right: '0px',
          bottom: '0px',
          left: '0px'
        }
      });

      console.log(`✅ PDF successfully generated at: ${outputPath}`);
      return outputPath;

    } catch (error) {
      console.error(`❌ PDF Generation Error: ${error.message}`);
      throw error;
    } finally {
      if (browser) {
        await browser.close();
      }
    }
  }
}

module.exports = new PDFService();
