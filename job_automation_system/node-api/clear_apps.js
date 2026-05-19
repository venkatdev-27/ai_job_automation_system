const { MongoClient } = require('mongodb');

async function clearOldApps() {
  const client = new MongoClient('mongodb+srv://kosurivenky:venkyyamuna@cluster0.uhbfag1.mongodb.net/ai_bot_resumes?appName=Cluster0');
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