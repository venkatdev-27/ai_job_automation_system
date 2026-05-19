const mongoose = require('mongoose');
require('./config/db');
const Student = require('./models/Student');

Student.find({}, 'name email resumeUrl student_id skills').then(students => {
  console.log('Total students:', students.length);
  students.forEach(s => {
    console.log('---');
    console.log('Name:', s.name);
    console.log('Email:', s.email);
    console.log('Student ID:', s.student_id);
    console.log('Resume URL:', s.resumeUrl);
    console.log('Skills:', s.skills ? s.skills.length : 0);
  });
  process.exit(0);
}).catch(err => { console.error(err); process.exit(1); });