// Job.js - Mongoose Model Skeleton
const mongoose = require('mongoose');

const jobSchema = new mongoose.Schema(
  {
    // TODO: define job fields (title, company, description, skills, etc.)
  },
  { timestamps: true }
);

module.exports = mongoose.model('Job', jobSchema);
