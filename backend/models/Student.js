// Student.js - Mongoose Model Skeleton
const mongoose = require('mongoose');
const crypto = require('crypto');

const credentialSchema = new mongoose.Schema(
  {
    username: { type: String, default: '' },
    password: { type: String, default: '' }, // NOTE: encrypt before storing in prod
  },
  { _id: false }
);

// Generate unique student_id
const generateStudentId = (email) => {
  const hash = crypto.createHash('md5').update(email).digest('hex');
  return `student_${hash.substring(0, 8)}`;
};

const studentSchema = new mongoose.Schema(
  {
    // Unique student ID for role management
    student_id: {
      type: String,
      unique: true,
      default: function() {
        return generateStudentId(this.email);
      }
    },
    name: {
      type: String,
      required: [true, 'Full name is required'],
      trim: true,
    },
    email: {
      type: String,
      required: [true, 'Email is required'],
      unique: true,
      lowercase: true,
      trim: true,
    },
    phone: {
      type: String,
      required: [true, 'Phone number is required'],
      trim: true,
    },
    gender: {
      type: String,
      enum: ['Male', 'Female', 'Other', 'Prefer not to say'],
      required: [true, 'Gender is required'],
    },
    location: {
      type: String,
      default: '',
    },
    years_experience: {
      type: String,
      default: '0',
    },
    // Skills extracted from resume
    skills: [{
      type: String,
    }],
    education: [{
      degree: { type: String, default: '' },
      institution: { type: String, default: '' },
      year: { type: String, default: '' }
    }],
    // Resume stored in Cloudinary
    resume: {
      type: String, // Cloudinary URL
      default: null,
    },
    cloudinary_public_id: {
      type: String,
      default: null,
    },
    resume_filename: {
      type: String,
      default: null,
    },
    // Job search preferences
    preferred_locations: [{
      type: String,
    }],
    candidate_titles: [{
      type: String,
    }],
    credentials: {
      linkedin:     { type: credentialSchema, default: {} },
      naukri:       { type: credentialSchema, default: {} },
      foundit:      { type: credentialSchema, default: {} },
    },
    // Resume parsed data from Python
    resumeData: {
      type: Object,
      default: null,
    },
    // Role configuration
    role_config_id: {
      type: String,
      default: null,
    },
    roles_generated: {
      type: Boolean,
      default: false,
    },
    // Status
    status: {
      type: String,
      enum: ['active', 'inactive', 'pending'],
      default: 'active',
    },
  },
  { timestamps: true }
);

// Generate student_id before saving
studentSchema.pre('save', function() {
  if (!this.student_id) {
    this.student_id = generateStudentId(this.email);
  }
});

module.exports = mongoose.model('Student', studentSchema);
