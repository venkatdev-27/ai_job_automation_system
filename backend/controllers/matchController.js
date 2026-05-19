const ragService = require('../services/ragService');
const resumeBuilderService = require('../services/resumeBuilderService');

/**
 * Run LangChain HYDE RAG Matching
 * POST /api/match
 */
const matchJobWithResume = async (req, res) => {
  try {
    const { jobDescription, resumeText, resumePath } = req.body;

    if (!jobDescription) {
      return res.status(400).json({ success: false, message: 'jobDescription is required' });
    }

    if (!resumeText && !resumePath) {
      return res.status(400).json({ success: false, message: 'Either resumeText or resumePath is required' });
    }

    // Call the python-based RAG LangChain pipeline
    const result = await ragService.matchResumeWithJob(jobDescription, resumeText, resumePath);

    return res.status(200).json({
      success: true,
      data: result,
    });
  } catch (error) {
    console.error('[matchController] Error in matching:', error.message);
    return res.status(500).json({
      success: false,
      message: 'Failed to run LangChain RAG Matching',
      error: error.message,
    });
  }
};

/**
 * Generate ATS-Optimized Tailored Resume
 * POST /api/match/generate-resume
 */
const generateAtsResume = async (req, res) => {
  try {
    const { jobDescription, retrievedChunks } = req.body;

    if (!jobDescription || !retrievedChunks) {
      return res.status(400).json({ success: false, message: 'Both jobDescription and retrievedChunks are required.' });
    }

    const result = await resumeBuilderService.buildTailoredResume(jobDescription, retrievedChunks);

    return res.status(200).json({
      success: true,
      ...result,
    });
  } catch (error) {
    console.error('[matchController] Error in resume generation:', error.message);
    return res.status(500).json({
      success: false,
      message: 'Failed to generate tailored resume',
      error: error.message,
    });
  }
};

module.exports = {
  matchJobWithResume,
  generateAtsResume,
};
