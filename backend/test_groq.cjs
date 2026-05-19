require('dotenv').config({ path: require('path').join(__dirname, '.env') });
const Groq = require('groq');

async function testGroqAPI() {
  console.log('Testing GroQ API Key...\n');

  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    console.error('❌ GROQ_API_KEY not found in .env');
    process.exit(1);
  }

  console.log(`✅ API Key found: ${apiKey.substring(0, 10)}...`);

  try {
    const groq = new Groq({ apiKey });

    const prompt = `Extract this resume into JSON format:
John Doe
Email: john.doe@email.com
Phone: 123-456-7890
Education: BS Computer Science at MIT 2020
Experience: Software Engineer at Google 2020-2023
Skills: JavaScript, Python, React

Return ONLY valid JSON with these fields: name, email, phone, education (array with degree, institution, year), experience (array with role, company, duration, summary), skills (array)`;

    console.log('\n🔄 Sending test prompt to GroQ...');

    const chat = await groq.chat.completions.create({
      model: 'llama-3.1-70b-versatile',
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.1,
      response_format: { type: 'json_object' }
    });

    const aiText = chat.choices[0]?.message?.content;

    if (!aiText) {
      throw new Error('No response from GroQ');
    }

    const parsed = JSON.parse(aiText);

    console.log('\n✅ API Response:');
    console.log(JSON.stringify(parsed, null, 2));

    return parsed;
  } catch (error) {
    console.error('\n❌ Error:', error.message);
    throw error;
  }
}

testGroqAPI()
  .then(() => {
    console.log('\n✅ Test passed!');
    process.exit(0);
  })
  .catch((err) => {
    console.error('\n❌ Test failed!');
    process.exit(1);
  });