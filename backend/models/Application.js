const mongoose = require('mongoose');

const applicationSchema = new mongoose.Schema(
  {
    studentId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Student',
      required: false,
    },
    jobTitle: {
      type: String,
      required: true,
      trim: true,
    },
    company: {
      type: String,
      required: true,
      trim: true,
    },
    candidateName: {
      type: String,
      trim: true,
      default: '',
    },
    candidateEmail: {
      type: String,
      trim: true,
      lowercase: true,
      default: '',
    },
    location: String,
    platform: {
      type: String,
      enum: ['LinkedIn', 'Naukri', 'Foundit'],
      required: true,
    },
    status: {
      type: String,
      enum: ['applied', 'interviewing', 'accepted', 'rejected', 'failed', 'pending', 'skipped', 'duplicate'],
      default: 'applied',
    },
    resumeUrl: {
      type: String, // Cloudinary URL
      default: '',
    },
    jobUrl: {
      type: String,
      default: '',
    },
    sourceJobId: {
      type: String,
      default: '',
    },
    jobDescription: String,
    atsScore: Number,
    appliedAt: {
      type: Date,
      default: Date.now,
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Application', applicationSchema);
