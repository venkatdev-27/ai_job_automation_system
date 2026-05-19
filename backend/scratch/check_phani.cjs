const mongoose = require('mongoose');
const connectDB = require('../config/db');
const Student = require('../models/Student');

async function run() {
  await connectDB();
  
  const total = await Student.countDocuments();
  console.log(`Total students: ${total}`);
  
  const phanis = await Student.find({ name: /phani/i });
  console.log(`Found ${phanis.length} student(s) with name containing 'phani':`);
  phanis.forEach(s => {
    console.log(`- Name: ${s.name}, Email: ${s.email}, _id: ${s._id}, student_id: ${s.student_id}`);
  });
  
  process.exit(0);
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
