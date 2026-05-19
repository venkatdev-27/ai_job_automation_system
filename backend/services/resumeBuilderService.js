const { spawn } = require('child_process');
const path = require('path');

/**
 * Executes the Python resume_builder.py script to generate an ATS-optimized resume.
 * @param {string} jobDescription - Job description text.
 * @param {string} retrievedChunks - Concatenated retrieved resume segments.
 * @returns {Promise<object>} The generated resume text and scoring details.
 */
exports.buildTailoredResume = (jobDescription, retrievedChunks) => {
  return new Promise((resolve, reject) => {
    const pythonScript = path.resolve(__dirname, '../../ai_engine/bot.py');
    const venvPython = path.resolve(__dirname, '../../.venv/Scripts/python.exe');

    const inputPayload = JSON.stringify({
      jobDescription,
      retrievedChunks
    });

    // Pass environment variables (GROQ_API_KEY)
    const env = { ...process.env };
    if (!env.GROQ_API_KEY) {
      return reject(new Error("GROQ_API_KEY not set in environment."));
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

    pythonProcess.stderr.on('data', (data) => {
      console.error(`DIAGNOSTIC: Python Stderr: ${data.toString()}`);
    });

    pythonProcess.stdin.write(inputPayload);
    pythonProcess.stdin.end();

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`Python resume_crew.py exited with code ${code}`));
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
          return reject(new Error(`CrewAI pipeline failed: ${result.error}`));
        }
        resolve(result);
      } catch (err) {
        reject(new Error(`Failed to parse Python result: ${err.message}`));
      }
    });

    pythonProcess.on('error', (err) => {
      reject(new Error(`Failed to start subprocess: ${err.message}`));
    });
  });
};
