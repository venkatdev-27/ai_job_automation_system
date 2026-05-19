// Re-extract skills using backend Node.js - fixed
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const mongoose = require('mongoose');
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log('MongoDB connected'))
  .catch(err => console.error('MongoDB error:', err));

const Student = require('./models/Student');

async function extractSkills() {
  // Get student
  const student = await Student.findOne({ student_id: 'student_65a834b8' });
  console.log('Student:', student.name);
  
  // Find the most recent Venkat Kosuri resume from uploads
  const uploadsDir = path.join(__dirname, 'uploads');
  const files = fs.readdirSync(uploadsDir);
  
  // Filter for Venkat Kosuri PDFs
  const venkatFiles = files.filter(f => f.includes('Venkat_Kosuri') && f.endsWith('.pdf'));
  
  if (venkatFiles.length === 0) {
    console.log('No local files found');
    process.exit(1);
  }
  
  // Get the most recent file
  const recentFile = venkatFiles.sort().pop();
  const filePath = path.join(uploadsDir, recentFile);
  console.log('Using file:', recentFile);
  
  // Use resume service to parse
  const resumeService = require('./services/resumeService');
  
  try {
    console.log('Extracting...');
    const result = await resumeService.parseResumeToJSON(filePath);
    console.log('Skills found:', result.skills.length);
    console.log('Skills:', result.skills);
    
    if (result && result.skills) {
      // Convert education array to string if needed
      let educationStr = '';
      if (result.education) {
        if (Array.isArray(result.education)) {
          educationStr = result.education.map(e => 
            `${e.degree} at ${e.institution} (${e.year})`
          ).join(', ');
        } else {
          educationStr = String(result.education);
        }
      }
      
      // Update student skills
      await Student.findByIdAndUpdate(student._id, {
        skills: result.skills,
        resumeData: {
          name: result.name,
          email: result.email,
          phone: result.phone,
          education: result.education,
          experience: result.experience,
          skills: result.skills
        },
        education: educationStr
      });
      console.log('Skills updated in MongoDB!');
    }
  } catch (err) {
    console.error('Extraction error:', err.message);
  }
  
  // Verify
  const updated = await Student.findOne({ student_id: 'student_65a834b8' });
  console.log('Final skills:', updated.skills);
  console.log('Skills count:', updated.skills.length);
  
  process.exit(0);
}

extractSkills();