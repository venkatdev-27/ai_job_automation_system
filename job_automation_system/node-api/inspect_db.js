const { MongoClient } = require('mongodb');
const uri = process.env.MONGO_URI || 'mongodb://localhost:27017/job_automation';
const client = new MongoClient(uri);
async function run() {
  try {
    await client.connect();
    const db = client.db('ai_bot_resumes');
    const colls = await db.listCollections().toArray();
    console.log('--- Collections in ai_bot_resumes ---');
    for (let c of colls) {
      const count = await db.collection(c.name).countDocuments();
      console.log(`${c.name}: ${count} documents`);
    }
  } catch (err) {
    console.error(err);
  } finally {
    await client.close();
  }
}
run();
