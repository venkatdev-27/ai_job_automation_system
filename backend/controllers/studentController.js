// studentController.js
const fs = require('fs');
const crypto = require('crypto');
const { v2: cloudinary } = require('cloudinary');
const Student = require('../models/Student');
const resumeService = require('../services/resumeService');
const roleService = require('../services/studentRoleService');

// Generate unique student_id
function generateStudentId(email) {
  const hash = crypto.createHash('md5').update(email).digest('hex');
  return `student_${hash.substring(0, 8)}`;
}

// ─────────────────────────────────────────────
// POST /api/students/register
// ─────────────────────────────────────────────
const registerStudent = async (req, res) => {
  try {
    // Use let for variables that might be reassigned
    let {
      name, email, phone, gender,
      location, years_experience, skills, education,
      preferred_locations, candidate_titles,
      linkedinUsername, linkedinPassword,
      naukriUsername,   naukriPassword,
      founditUsername,  founditPassword,
    } = req.body;

    // Basic validation
    if (!name || !email || !phone || !gender) {
      if (req.file) {
        fs.unlink(req.file.path, () => {});
      }
      return res.status(400).json({ success: false, message: 'Please provide all required fields (name, email, phone, gender).' });
    }

    // Generate unique student_id
    const student_id = generateStudentId(email);

    // Build credentials object
    const credentials = {
      linkedin:    { username: linkedinUsername    || '', password: linkedinPassword    || '' },
      naukri:      { username: naukriUsername      || '', password: naukriPassword      || '' },
      foundit:     { username: founditUsername     || '', password: founditPassword     || '' },
    };

    // File handling
    let resumeUrl = null;
    let cloudinaryPublicId = null;
    let resumeFilename = null;
    let parsedSkills = skills || [];
    let resumeData = null;

    if (req.file) {
      try {
        resumeFilename = req.file.originalname;
        
        // Step 1: Extract data using Python
        try {
          resumeData = await resumeService.parseResumeToJSON(req.file.path);
          // Extract skills from parsed data
          if (resumeData && resumeData.skills && Array.isArray(resumeData.skills)) {
            parsedSkills = resumeData.skills;
          }
          // Also get education if not provided
          if (!education && resumeData && resumeData.education) {
            education = resumeData.education;
          }
        } catch (extractionError) {
          console.error('[Resume Extraction Warning]', extractionError.message);
        }

        // Step 2: Upload to Cloudinary (per-student folder)
        const uploadResult = await cloudinary.uploader.upload(req.file.path, {
          folder: `resumes/${student_id}`,  // Per-student folder!
          resource_type: 'raw',  // Use raw for PDF/DOC files
          public_id: `${student_id}_resume`
        });

        resumeUrl = uploadResult.secure_url;
        cloudinaryPublicId = uploadResult.public_id;

        // Step 3: Clean up local file
        fs.unlink(req.file.path, (err) => {
          if (err) console.error('[Local File Cleanup Error]', err.message);
        });

      } catch (err) {
        console.error('[Cloudinary/Extraction Error]', err.message);
      }
    }

    // Use provided skills or parsed skills
    const finalSkills = skills || parsedSkills || [];

    // Create student
    const student = new Student({
      student_id,
      name,
      email,
      phone,
      gender,
      location: location || '',
      years_experience: years_experience || '0',
      skills: finalSkills,
      education: education || [],
      preferred_locations: preferred_locations || [],
      candidate_titles: candidate_titles || [],
      resume: resumeUrl,
      cloudinary_public_id: cloudinaryPublicId,
      resume_filename: resumeFilename,
      resumeData,
      credentials,
      status: 'active'
    });

    await student.save();

    // Step 4: Generate roles immediately (if skills exist)
    let roleConfig = null;
    if (finalSkills.length > 0) {
      try {
        roleConfig = await roleService.generateStudentRoleConfig(student_id, finalSkills);
        
        // Update student with role_config_id
        await Student.findByIdAndUpdate(student._id, {
          role_config_id: roleConfig.role_config_id,
          roles_generated: true
        });
        
      } catch (roleError) {
        console.error('[Role Generation Error]', roleError.message);
      }
    }

    // Step 5: Trigger AI Engine Warmup Pipeline (Stage 1 Tailoring)
    // This runs in the background on the Python API server
    try {
      console.log(`[Warmup] Triggering AI Engine warmup for ${student_id}...`);
      // Use dynamic import for fetch if needed, or assume global fetch (Node 18+)
      fetch('http://localhost:8002/warmup-student', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id })
      }).catch(err => console.error('[Warmup Trigger Async Error]', err.message));
      
      console.log(`[Warmup] Trigger sent successfully to AI Engine.`);
    } catch (warmupError) {
      console.error('[Warmup Trigger Error]', warmupError.message);
      // We don't fail the registration if warmup trigger fails
    }

    res.status(201).json({
      success: true,
      message: 'Student registered successfully!',
      data: {
        id: student._id,
        student_id: student.student_id,
        name: student.name,
        email: student.email,
        resume_url: student.resume,
        skills_count: finalSkills.length,
        roles_generated: roleConfig ? true : false,
        role_config_id: roleConfig?.role_config_id || null
      },
    });
  } catch (err) {
    // Handle mongoose duplicate email
    if (err.code === 11000) {
      return res.status(409).json({ success: false, message: 'Email already registered.' });
    }
    console.error('[registerStudent]', err.message);
    res.status(500).json({ success: false, message: 'Server error. Please try again.' });
  }
};

// ─────────────────────────────────────────────
// GET /api/students
// ─────────────────────────────────────────────
const getAllStudents = async (req, res) => {
  try {
    const students = await Student.find().select('-credentials');
    res.json({ success: true, data: students });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

// ─────────────────────────────────────────────
// GET /api/students/:id
// ─────────────────────────────────────────────
const getStudentById = async (req, res) => {
  try {
    const student = await Student.findById(req.params.id).select('-credentials');
    if (!student) return res.status(404).json({ success: false, message: 'Student not found' });
    res.json({ success: true, data: student });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

// ─────────────────────────────────────────────
// DELETE /api/students/:id
// ─────────────────────────────────────────────
const deleteStudent = async (req, res) => {
  try {
    await Student.findByIdAndDelete(req.params.id);
    res.json({ success: true, message: 'Student deleted' });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

module.exports = { registerStudent, getAllStudents, getStudentById, deleteStudent };
