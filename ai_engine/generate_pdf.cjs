const fs = require('fs');
const path = require('path');
const pdfService = require('../backend/services/pdfService');

/**
 * CLI Wrapper for PDF Generation
 * Usage: node generate_pdf.js <html_path> <output_path>
 */
async function run() {
    const args = process.argv.slice(2);
    if (args.length < 2) {
        console.error('Usage: node generate_pdf.js <html_path> <output_path>');
        process.exit(1);
    }

    const htmlPath = args[0];
    const outputPath = args[1];

    try {
        const htmlContent = fs.readFileSync(htmlPath, 'utf8');
        await pdfService.generatePDFFromHTML(htmlContent, outputPath);
        console.log(`PDF_SUCCESS: ${outputPath}`);
    } catch (error) {
        console.error(`PDF_ERROR: ${error.message}`);
        process.exit(1);
    }
}

run();
