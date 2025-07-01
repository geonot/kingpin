# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
# Ensure this is set to False in production overrides
ENV FLASK_DEBUG=True
# Default port, can be overridden by CMD or docker run -p
ENV APP_PORT=5000

# Install system dependencies
# - postgresql-client for pg_isready
# - libpq-dev and build-essential for compiling psycopg2 if needed
# - curl for potential health checks or other utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup -s /bin/bash appuser

# Create directories for app and set permissions
RUN mkdir -p /home/appuser/web/instance && \
    chown -R appuser:appgroup /home/appuser/web
WORKDIR /home/appuser/web

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entrypoint script and make it executable
# This script will be created in the next step
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh && chown appuser:appgroup docker-entrypoint.sh

# Copy the rest of the application code as the non-root user
# Ensure .dockerignore is properly set up to exclude .venv, __pycache__, etc.
COPY --chown=appuser:appgroup . .

# Switch to the non-root user
USER appuser

# Expose the port the app runs on
EXPOSE ${APP_PORT}

# Set the entrypoint script
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command to run when the container starts
# The entrypoint script will ultimately execute this or a similar command.
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
