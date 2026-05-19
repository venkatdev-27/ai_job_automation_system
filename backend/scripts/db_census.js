const mongoose = require('mongoose');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.resolve(__dirname, '../.env') });

async function census() {
  await mongoose.connect(process.env.MONGO_URI);
  console.log('Connected to MongoDB');

  const students = await mongoose.connection.db.collection('students').find({}).toArray();
  console.log(`Checking ${students.length} students...`);

  for (let s of students) {
    const chunkCounts = {};
    
    // Check various common field names for relationships
    const fieldsToCheck = ['studentId', 'userId', 'student_id', 'user_id', 'email'];
    
    for (let field of fieldsToCheck) {
      const val = (field === 'email') ? s.email : s._id;
      const count = await mongoose.connection.db.collection('resume_chunks').countDocuments({ [field]: val });
      if (count > 0) chunkCounts[field] = count;
      
      const countStr = await mongoose.connection.db.collection('resume_chunks').countDocuments({ [field]: s._id.toString() });
      if (countStr > 0) chunkCounts[`${field} (string)`] = countStr;
    }

    console.log(`- ${s.name} (${s.email}) [ID: ${s._id.toString()}]:`, Object.keys(chunkCounts).length > 0 ? chunkCounts : 'NO CHUNKS');
  }

  process.exit(0);
}

census();
