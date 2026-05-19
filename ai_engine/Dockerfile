# Use an official Python runtime with Playwright pre-installed
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies (Playwright browsers and system deps are already included)
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium --with-deps && \
    rm -rf /root/.cache/pip && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /ms-playwright/.cache

# Copy the rest of the application code
COPY . ./ai_engine

# Expose the API port
EXPOSE 8000

# Start the application with Uvicorn
CMD ["uvicorn", "ai_engine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
