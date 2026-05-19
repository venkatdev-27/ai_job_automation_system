require('dotenv').config({ path: require('path').join(__dirname, '.env') });
const { GoogleGenerativeAI } = require('@google/generative-ai');

async function testGeminiAPI() {
  console.log('Testing Gemini API Key with resume parsing...\n');

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    console.error('❌ GEMINI_API_KEY not found in .env');
    process.exit(1);
  }

  console.log(`✅ API Key found: ${apiKey.substring(0, 10)}...`);

  try {
    const ai = new GoogleGenerativeAI(apiKey);

    const model = ai.getGenerativeModel({
      model: 'gemini-2.5-flash',
      generationConfig: {
        responseMimeType: "application/json",
      }
    });

    const prompt = `You are an expert ATS (Applicant Tracking System) JSON parser.
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
John Doe
Email: john.doe@email.com
Phone: 123-456-7890
Education: BS Computer Science at MIT 2020
Experience: Software Engineer at Google 2020-2023
Skills: JavaScript, Python, React`;

    console.log('\n🔄 Sending resume parsing prompt to Gemini...');

    const result = await model.generateContent(prompt);
    const aiText = result.response.text();

    const cleanlyParsed = aiText.replace(/```json/g, '').replace(/```/g, '').trim();
    const parsed = JSON.parse(cleanlyParsed);

    console.log('\n✅ API Response:');
    console.log(JSON.stringify(parsed, null, 2));

    return parsed;
  } catch (error) {
    console.error('\n❌ Error:', error.message);
    if (error.message.includes('API_KEY')) {
      console.error('Invalid or expired API key');
    }
    throw error;
  }
}

testGeminiAPI()
  .then(() => {
    console.log('\n✅ Test passed!');
    process.exit(0);
  })
  .catch((err) => {
    console.error('\n❌ Test failed!');
    process.exit(1);
  });