const { MongoClient } = require('mongodb');

async function checkStudents() {
  const client = new MongoClient(process.env.MONGO_URI || 'mongodb://localhost:27017/job_automation');
  await client.connect();
  const db = client.db('ai_bot_resumes');
  
  const students = await db.collection('students').find({}).toArray();
  console.log('=== REMAINING STUDENTS ===');
  console.log('Total:', students.length);
  
  for (const s of students) {
    console.log('\nName:', s.name);
    console.log('Email:', s.email);
    console.log('Student ID:', s.student_id);
    console.log('Credentials:', s.credentials ? 'yes' : 'no');
    if (s.credentials) {
      console.log('  Naukri:', s.credentials.naukri);
      console.log('  LinkedIn:', s.credentials.linkedin);
      console.log('  FoundIt:', s.credentials.foundit);
    }
  }
  
  await client.close();
}

checkStudents().catch(console.error);