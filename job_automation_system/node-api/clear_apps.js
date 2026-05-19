const { MongoClient } = require('mongodb');

async function clearOldApps() {
  const client = new MongoClient(process.env.MONGO_URI || 'mongodb://localhost:27017/job_automation');
  await client.connect();
  const db = client.db('ai_bot_resumes');
  
  // Keep only pending applications (to try again)
  const result = await db.collection('job_applications').deleteMany({
    status: { $in: ['applied', 'failed', 'skipped', 'duplicate'] }
  });
  console.log('Deleted old applications:', result.deletedCount);
  
  // Also clear Redis queues
  console.log('\nClearing Redis queues...');
  
  // Get collection stats
  const remaining = await db.collection('job_applications').countDocuments();
  console.log('Remaining applications:', remaining);
  
  await client.close();
}

clearOldApps().catch(console.error);