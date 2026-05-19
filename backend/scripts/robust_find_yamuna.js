const mongoose = require('mongoose');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.resolve(__dirname, '../.env') });

async function findYamuna() {
  await mongoose.connect(process.env.MONGO_URI);
  console.log('Connected to MongoDB');

  // Search by content for "Yamuna"
  const chunk = await mongoose.connection.db.collection('resume_chunks').findOne({ 
    content: { $regex: /yamuna/i } 
  });

  if (chunk) {
    console.log('FOUND YAMUNA CHUNK!');
    console.log('Chunk ID:', chunk._id.toString());
    console.log('Student ID:', chunk.studentId ? chunk.studentId.toString() : 'NONE');
    console.log('Email:', chunk.email ? chunk.email : 'NONE');
    
    // Fetch all chunks for this context
    const sid = chunk.studentId || chunk.email;
    const key = chunk.studentId ? 'studentId' : 'email';
    
    const allChunks = await mongoose.connection.db.collection('resume_chunks')
      .find({ [key]: sid })
      .toArray();
      
    console.log(`Verified ${allChunks.length} related chunks.`);
    
    const fullText = allChunks.sort((a,b) => (a.chunkIndex || 0) - (b.chunkIndex || 0))
      .map(c => c.content)
      .join('\n\n');
      
    console.log('--- SAMPLE CONTENT ---');
    console.log(fullText.substring(0, 500));
    console.log('--- END SAMPLE ---');
  } else {
    console.log('NO Resume Chunk found containing "Yamuna".');
    
    // Fallback: search ALL chunks for ANY mani
    const maniChunk = await mongoose.connection.db.collection('resume_chunks').findOne({ 
      content: { $regex: /mani kumar/i } 
    });
    if (maniChunk) {
      console.log('FOUND MANI CHUNK! StudentID:', maniChunk.studentId?.toString());
    } else {
      console.log('NO Resume Chunk found containing "Mani Kumar".');
    }
  }

  process.exit(0);
}

findYamuna();
