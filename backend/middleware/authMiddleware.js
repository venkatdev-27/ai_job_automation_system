// authMiddleware.js
// Validates JWT tokens for protected routes

const jwt = require('jsonwebtoken');
const { JWT_SECRET } = require('../config/env');

const protect = (req, res, next) => {
  // TODO: implement JWT verification
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ message: 'Unauthorized - No token provided' });
  }

  try {
    const token = authHeader.split(' ')[1];
    // const decoded = jwt.verify(token, JWT_SECRET);
    // req.user = decoded;
    next();
  } catch (err) {
    return res.status(401).json({ message: 'Unauthorized - Invalid token' });
  }
};

module.exports = { protect };
