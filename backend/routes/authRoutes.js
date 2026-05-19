// authRoutes.js
const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');
const Student = require('../models/Student');
const { JWT_SECRET } = require('../config/env');

const asyncHandler = (fn) => (req, res, next) =>
  Promise.resolve(fn(req, res, next)).catch(next);

// POST /api/auth/register
router.post('/register', asyncHandler(async (req, res) => {
  const { name, email, phone, password, gender } = req.body;

  if (!name || !email || !phone || !password || !gender) {
    return res.status(400).json({ success: false, message: 'Please provide all required fields.' });
  }

  const existingStudent = await Student.findOne({ email });
  if (existingStudent) {
    return res.status(400).json({ success: false, message: 'Email already registered.' });
  }

  const student = new Student({
    name,
    email,
    phone,
    gender,
    credentials: {
      linkedin: { username: '', password: '' },
      naukri: { username: '', password: '' },
      foundit: { username: '', password: '' },
    },
  });

  await student.save();

  const token = jwt.sign({ studentId: student.student_id, email: student.email }, JWT_SECRET, { expiresIn: '7d' });

  res.status(201).json({
    success: true,
    message: 'Registration successful',
    token,
    student: {
      student_id: student.student_id,
      name: student.name,
      email: student.email,
    },
  });
}));

// POST /api/auth/login
router.post('/login', asyncHandler(async (req, res) => {
  const { email, password } = req.body;

  if (!email || !password) {
    return res.status(400).json({ success: false, message: 'Please provide email and password.' });
  }

  const student = await Student.findOne({ email });
  if (!student) {
    return res.status(401).json({ success: false, message: 'Invalid credentials.' });
  }

  const token = jwt.sign({ studentId: student.student_id, email: student.email }, JWT_SECRET, { expiresIn: '7d' });

  res.json({
    success: true,
    message: 'Login successful',
    token,
    student: {
      student_id: student.student_id,
      name: student.name,
      email: student.email,
    },
  });
}));

module.exports = router;