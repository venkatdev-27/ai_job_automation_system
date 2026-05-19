import axios from 'axios';
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '' });

export const fetchStats = () => api.get('/api/stats').then(r => r.data);
export const fetchChartData = (tf = '7d') => api.get(`/api/stats/chart?timeframe=${tf}`).then(r => r.data);
export const fetchPlatforms = () => api.get('/api/stats/platforms').then(r => r.data);
export const fetchApplications = (tf = 'all') => api.get(`/api/applications?timeframe=${tf}`).then(r => r.data);
export const fetchStudents = () => api.get('/api/students').then(r => r.data);
export const fetchStudentDetail = (id) => api.get(`/api/students/${id}`).then(r => r.data);
export const fetchHealth = () => api.get('/api/system/health').then(r => r.data);

// Automation toggle API
export const fetchAutomationStatus = () => api.get('/api/automation/status').then(r => r.data);
export const toggleAutomation = (status, auto_enable) => 
  api.post('/api/automation/toggle', { status, auto_enable }).then(r => r.data);
export const updateAutomationSettings = (settings) => 
  api.post('/api/automation/settings', settings).then(r => r.data);
export const updateJobsCount = (jobs_running, jobs_completed_today) => 
  api.post('/api/automation/jobs-count', { jobs_running, jobs_completed_today }).then(r => r.data);
export const triggerJobRun = () => 
  api.post('/api/automation/run').then(r => r.data);

export default api;
