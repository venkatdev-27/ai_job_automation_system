const { spawn } = require('child_process');
const path = require('path');

/**
 * Calls the python script `rag_matcher.py` with the provided job description and candidate resume.
 * @param {string} jobDescription - Job description text.
 * @param {string} resumeText - Raw text of the resume (or pass resumePath instead).
 * @param {string} resumePath - Path to the PDF file (alternative to resumeText).
 * @returns {Promise<Object>} The parsed JSON matching result.
 */
exports.matchResumeWithJob = (jobDescription, resumeText = null, resumePath = null) => {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, '../scripts/rag_matcher.py');
    // Using the python executable from the virtual environment if possible, or fallback to global
    // Try to resolve the virtualenv python
    const venvPython = path.resolve(__dirname, '../../.venv/Scripts/python.exe');

    const inputPayload = JSON.stringify({
      jobDescription,
      resumeText,
      resumePath
    });

    // Include GOOGLE_API_KEY from GEMINI_API_KEY if needed by LangChain
    const env = { ...process.env };
    if (env.GEMINI_API_KEY && !env.GOOGLE_API_KEY) {
      env.GOOGLE_API_KEY = env.GEMINI_API_KEY;
    }

    const pythonProcess = spawn(venvPython, [pythonScript], { env });

    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => {
      stdoutData += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderrData += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`Python process exited with code ${code}. Stderr: ${stderrData}`));
      }

      try {
        const startMarker = '===JSON_START===';
        const endMarker = '===JSON_END===';
        const startIndex = stdoutData.indexOf(startMarker);
        const endIndex = stdoutData.indexOf(endMarker);

        if (startIndex === -1 || endIndex === -1) {
          throw new Error(`No valid success markers found in Python output. Raw: ${stdoutData.slice(-500)}`);
        }
        
        const jsonStr = stdoutData.substring(startIndex + startMarker.length, endIndex);
        const result = JSON.parse(jsonStr);
        if (result.success === false) {
          return reject(new Error(result.error || 'Unknown error from Python script'));
        }
        resolve(result.data ? result.data : result);
      } catch (err) {
        reject(new Error(`Failed to parse Python result: ${err.message}`));
      }
    });

    pythonProcess.on('error', (err) => {
      // If .venv python fails, maybe we can fallback to global python in a more robust way, 
      // but for now we reject
      reject(new Error(`Failed to start subprocess: ${err.message}`));
    });

    // Write payload to stdin
    pythonProcess.stdin.write(inputPayload);
    pythonProcess.stdin.end();
  });
};
