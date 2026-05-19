const { MongoClient } = require('mongodb');
const uri = 'mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=Cluster0';
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
