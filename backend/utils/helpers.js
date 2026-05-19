// helpers.js
// Reusable utility/helper functions

/**
 * Send a standardized success response
 */
const sendSuccess = (res, data, statusCode = 200) => {
  res.status(statusCode).json({ success: true, data });
};

/**
 * Send a standardized error response
 */
const sendError = (res, message, statusCode = 400) => {
  res.status(statusCode).json({ success: false, message });
};

module.exports = { sendSuccess, sendError };
