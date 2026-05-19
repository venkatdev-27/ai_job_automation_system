FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

LABEL maintainer="Job Automation System"
LABEL description="Production job application automation with Celery + Playwright"

# Set working directory
WORKDIR /app

# Install Chrome and dependencies BEFORE Python packages for better caching
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Download and install Chrome Stable
RUN wget -q -O /tmp/chrome-stable.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i /tmp/chrome-stable.deb || apt-get install -f -y \
    && rm /tmp/chrome-stable.deb \
    && ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies with extended timeout and retry
RUN pip config set global.trusted-host pypi.org && \
    pip config set global.trusted-host files.pythonhosted.org && \
    pip config set global.trusted-host pypi.python.org && \
    pip config set global.timeout 600 && \
    pip install --no-cache-dir -r requirements.txt

# Install Chromium browsers (base image already has playwright)
RUN python -m playwright install chromium && \
    rm -rf /root/.cache/pip

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_BROWSER=chromium \
    IN_DOCKER=true

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/chrome_profile /app/storage

# Expose port (default worker port, can be overridden at runtime)
EXPOSE 5555

# Default command
CMD ["celery", "-A", "celery_app.app", "worker", "-Q", "naukri,linkedin", "-c", "2", "--loglevel=info"]