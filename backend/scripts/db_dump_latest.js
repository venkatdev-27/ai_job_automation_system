const mongoose = require('mongoose');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.resolve(__dirname, '../.env') });

async function dump() {
  await mongoose.connect(process.env.MONGO_URI);
  console.log('Connected to MongoDB');

  const chunks = await mongoose.connection.db.collection('resume_chunks').find({}).sort({_id: -1}).limit(10).toArray();
  console.log(`Dumping latest ${chunks.length} chunks...`);

  chunks.forEach((c, i) => {
    console.log(`--- Chunk ${i+1} ---`);
    console.log('ID:', c._id.toString());
    console.log('Student ID:', c.studentId ? c.studentId.toString() : (c.userId ? c.userId.toString() : 'NONE'));
    console.log('Summary:', c.content ? c.content.substring(0, 300) : 'EMPTY CONTENT');
  });

  process.exit(0);
}

dump();
