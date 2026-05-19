const express = require('express');
const router = express.Router();
const { matchJobWithResume, generateAtsResume } = require('../controllers/matchController');

router.post('/', matchJobWithResume);
router.post('/generate-resume', generateAtsResume);

module.exports = router;
