import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:5000',
  // Don't set Content-Type here — let axios handle multipart/form-data boundaries automatically
});

export default api;
