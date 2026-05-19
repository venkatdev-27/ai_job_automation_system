const http = require('http');

const data = JSON.stringify({ jobs_per_student: 2, platforms: ['naukri'] });
const options = {
  hostname: 'localhost',
  port: 5000,
  path: '/api/automation/run',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': data.length
  }
};

const req = http.request(options, (res) => {
  let body = '';
  res.on('data', (chunk) => body += chunk);
  res.on('end', () => console.log(body));
});

req.on('error', (e) => console.error('Error:', e.message));
req.write(data);
req.end();