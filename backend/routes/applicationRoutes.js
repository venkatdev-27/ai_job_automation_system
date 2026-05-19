// applicationRoutes.js
const express = require('express');
const router = express.Router();
const {
  getAllApplications,
  getApplicationById,
  createApplication,
  logAutomationApplication,
  updateApplication,
  deleteApplication,
  getDashboardStats
} = require('../controllers/applicationController');

// const { protect } = require('../middleware/authMiddleware');

router.get('/stats', getDashboardStats);
router.post('/log-application', logAutomationApplication);
router.get('/', getAllApplications);
router.get('/:id', getApplicationById);
router.post('/', createApplication);
router.put('/:id', updateApplication);
router.delete('/:id', deleteApplication);

module.exports = router;
