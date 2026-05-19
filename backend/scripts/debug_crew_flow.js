require('dotenv').config({ path: '../.env' });
console.log("DEBUG: GROQ_API_KEY is", process.env.GROQ_API_KEY ? "PRESENT" : "MISSING");
const { buildTailoredResume } = require('../services/resumeBuilderService');

const mockJobDescription = "Senior Node.js Developer with 5+ years experience.";
const mockRetrievedChunks = "John Doe is a Senior Developer with 6 years experience in Node.js.";

async function runTest() {
  console.log("🚀 Testing CrewAI Resume Builder...");
  try {
    const result = await buildTailoredResume(mockJobDescription, mockRetrievedChunks);
    console.log("✅ Success!");
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.error("❌ Failed:", err.message);
  }
}

runTest();
