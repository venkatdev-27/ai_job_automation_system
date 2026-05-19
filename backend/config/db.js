const mongoose = require('mongoose');
const { MONGO_URI } = require('./env');

const connectDB = async () => {
  try {
    // Explicitly set the database name to ensure Atlas points exactly where intended
    await mongoose.connect(MONGO_URI, { dbName: 'ai_bot_resumes' });
    console.log('MongoDB connected ✅ [Database: ai_bot_resumes]');
  } catch (err) {
    console.error('MongoDB connection error:', err.message);
    process.exit(1);
  }
};

module.exports = connectDB;
