// studentRoutes.js
const express = require('express');
const router = express.Router();
const { upload } = require('../middleware/uploadMiddleware');
const {
  registerStudent,
  getAllStudents,
  getStudentById,
  deleteStudent,
} = require('../controllers/studentController');

// Async wrapper for error handling
const asyncHandler = (fn) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch(next);
};

// POST /api/students/register  — multipart
router.post('/register', upload.single('resume'), asyncHandler(registerStudent));

// GET /api/students
router.get('/', asyncHandler(getAllStudents));

// GET /api/students/:id
router.get('/:id', asyncHandler(getStudentById));

// DELETE /api/students/:id
router.delete('/:id', asyncHandler(deleteStudent));

module.exports = router;
