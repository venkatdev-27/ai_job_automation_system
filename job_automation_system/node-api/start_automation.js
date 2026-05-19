const http = require('http');

const data = JSON.stringify({ status: 'on' });
const options = {
  hostname: 'localhost',
  port: 5000,
  path: '/api/automation/toggle',
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