// studentRoleService.js
// Generates roles for students using rule-based approach

const mongoose = require('mongoose');
require('dotenv').config();

// Skill to role mappings (expanded)
const SKILL_TO_ROLE = {
  // JavaScript/Frontend
  'javascript': 'JavaScript Developer',
  'typescript': 'TypeScript Developer',
  'react': 'React Developer',
  'reactjs': 'React.js Developer',
  'angular': 'Angular Developer',
  'vue': 'Vue.js Developer',
  'jquery': 'jQuery Developer',
  'redux': 'Redux Developer',
  'nextjs': 'Next.js Developer',
  
  // Backend
  'nodejs': 'Node.js Developer',
  'node': 'Node.js Developer',
  'express': 'Express.js Developer',
  'python': 'Python Developer',
  'django': 'Django Developer',
  'flask': 'Flask Developer',
  'java': 'Java Developer',
  'spring': 'Spring Developer',
  'spring boot': 'Spring Boot Developer',
  
  // Database
  'mongodb': 'MongoDB Developer',
  'mysql': 'MySQL Developer',
  'postgresql': 'PostgreSQL Developer',
  'sql': 'SQL Developer',
  'redis': 'Redis Developer',
  
  // Cloud/DevOps
  'aws': 'AWS Developer',
  'azure': 'Azure Developer',
  'gcp': 'GCP Developer',
  'docker': 'Docker Developer',
  'kubernetes': 'Kubernetes Developer',
  'jenkins': 'Jenkins Developer',
  
  // Data/ML
  'pandas': 'Pandas Developer',
  'pyspark': 'PySpark Developer',
  'spark': 'Spark Developer',
  'machine learning': 'Machine Learning Engineer',
  'tensorflow': 'TensorFlow Developer',
  'pytorch': 'PyTorch Developer',
  
  // Mobile
  'react native': 'React Native Developer',
  'flutter': 'Flutter Developer',
  'android': 'Android Developer',
  'ios': 'iOS Developer',
  
  // API
  'rest': 'REST API Developer',
  'graphql': 'GraphQL Developer',
  'api': 'API Developer',
};

// Category roles
const CATEGORY_ROLES = {
  'frontend': ['Frontend Developer', 'Web Developer', 'UI Developer'],
  'backend': ['Backend Developer', 'Server Developer', 'API Developer'],
  'database': ['Database Developer', 'DBA'],
  'cloud': ['Cloud Engineer', 'DevOps Engineer'],
  'data': ['Data Engineer', 'ETL Developer'],
  'ml': ['ML Engineer', 'AI Engineer'],
};

// Role generation functions
function generateStudentRoles(userSkills) {
  if (!userSkills || userSkills.length === 0) {
    return getDefaultRoles();
  }
  
  const normalized = new Set(userSkills.map(s => s.toLowerCase().trim()));
  const roleSet = new Set();
  const roles = [];
  
  // Phase 1: Direct skill matches
  for (const skill of normalized) {
    if (SKILL_TO_ROLE[skill]) {
      roleSet.add(SKILL_TO_ROLE[skill]);
    }
  }
  
  // Phase 2: Category matches
  const hasFrontend = normalized.has('javascript') || normalized.has('react') || normalized.has('angular');
  const hasBackend = normalized.has('nodejs') || normalized.has('python') || normalized.has('java');
  const hasDB = normalized.has('mongodb') || normalized.has('mysql') || normalized.has('sql');
  
  if (hasFrontend && hasBackend) {
    roleSet.add('MERN Full Stack Developer');
    roleSet.add('Full Stack Developer');
  }
  
  if (hasFrontend) {
    roleSet.add('Frontend Developer');
    roleSet.add('Web Developer');
  }
  
  if (hasBackend) {
    roleSet.add('Backend Developer');
    roleSet.add('API Developer');
  }
  
  if (hasDB) {
    roleSet.add('Database Developer');
  }
  
  // Add defaults if too few
  if (roleSet.size < 3) {
    roleSet.add('Software Developer');
    roleSet.add('Full Stack Developer');
  }
  
  // Convert to array
  for (const role of roleSet) {
    roles.push({
      role_key: role.toLowerCase().replace(/[^a-z0-9]/g, '_'),
      title: role,
      generated_by: 'rule'
    });
  }
  
  return roles.slice(0, 6);
}

function getDefaultRoles() {
  return [
    { role_key: 'software_developer', title: 'Software Developer', generated_by: 'rule' },
    { role_key: 'full_stack_developer', title: 'Full Stack Developer', generated_by: 'rule' },
    { role_key: 'web_developer', title: 'Web Developer', generated_by: 'rule' },
  ];
}

// Generate search roles (30 per platform)
function generateSearchRoles(roles, platform) {
  const searchRoles = [];
  
  for (let i = 0; i < Math.min(30, roles.length * 3); i++) {
    const roleIndex = i % roles.length;
    searchRoles.push({
      role: roles[roleIndex].title,
      query_order: i + 1,
      platform: platform,
      generated_by: 'rule'
    });
  }
  
  return searchRoles;
}

// MongoDB connection - use existing mongoose connection
async function getMongoDb() {
  if (mongoose.connection.readyState !== 1) {
    throw new Error('Mongoose not connected');
  }
  return mongoose.connection.db;
}

// Save role config to MongoDB
async function saveRoleConfig(studentId, userSkills, resumeRoles) {
  const db = await getMongoDb();
  const collection = db.collection('role_configs');
  
  const searchRoles = {
    naukri: generateSearchRoles(resumeRoles, 'naukri'),
    linkedin: generateSearchRoles(resumeRoles, 'linkedin'),
    foundit: generateSearchRoles(resumeRoles, 'foundit')
  };
  
  const config = {
    candidate_id: studentId,
    user_skills: userSkills,
    resume_roles: resumeRoles,
    search_roles: searchRoles,
    pagination: {
      roles_per_page: 3,
      current_page: 1,
      platform_offsets: {}
    },
    generated_at: new Date().toISOString(),
    last_updated: new Date().toISOString(),
    expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    status: 'active'
  };
  
  const result = await collection.updateOne(
    { candidate_id: studentId },
    { $set: config },
    { upsert: true }
  );
  
  if (result.upsertedId) {
    return result.upsertedId.toString();
  }
  const existingConfig = await collection.findOne({ candidate_id: studentId });
  return existingConfig._id.toString();
}

// Main function: Generate roles for student
async function generateStudentRoleConfig(studentId, userSkills) {
  // Generate resume roles (6)
  const resumeRoles = generateStudentRoles(userSkills);
  
  // Save to MongoDB
  const roleConfigId = await saveRoleConfig(studentId, userSkills, resumeRoles);
  
  return {
    success: true,
    role_config_id: roleConfigId,
    resume_roles: resumeRoles,
    roles_count: resumeRoles.length
  };
}

module.exports = {
  generateStudentRoleConfig,
  generateStudentRoles,
  generateSearchRoles,
  getDefaultRoles
};