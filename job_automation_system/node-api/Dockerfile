FROM node:20-alpine

WORKDIR /app

# Install Docker and Docker Compose dependencies
RUN apk add --no-cache docker-cli docker-compose

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install --production

# Copy all application files
COPY server.js .
COPY .env .
COPY services/ ./services/

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 5000

# Start server
CMD ["node", "server.js"]