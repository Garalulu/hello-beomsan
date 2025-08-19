# Use official Python image to avoid mise issues
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies including LiteFS requirements
RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    fuse3 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install LiteFS
COPY --from=flyio/litefs:0.5 /usr/local/bin/litefs /usr/local/bin/litefs

# Set work directory
WORKDIR /code

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Copy LiteFS configuration
COPY litefs.yml /etc/litefs.yml

# LiteFS will manage the application startup
ENTRYPOINT ["litefs", "mount"]