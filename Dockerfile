# Hoopla-DL Docker Container
# Unified solution for downloading ebooks, comics, and audiobooks from Hoopla Digital
FROM debian:bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    yt-dlp \
    wget \
    curl \
    gnupg2 \
    ca-certificates \
    libc6 \
    libgcc-s1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Install bento4 for mp4decrypt (required for audiobook DRM decryption)
RUN wget -O /tmp/bento4.deb http://ftp.deb-multimedia.org/pool/main/b/bento4-dmo/bento4_1.6.0.640-dmo1_arm64.deb && \
    dpkg -i /tmp/bento4.deb || (apt-get update && apt-get install -fy) && \
    rm -f /tmp/bento4.deb && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN python3 -m pip install --break-system-packages --no-cache-dir -r requirements.txt

# Copy application files
COPY hoopla_main.py .
COPY widevine_keys/ ./widevine_keys/

# Create necessary directories with proper permissions
RUN mkdir -p /app/output /app/tmp /home/ezrapi/temp && \
    chmod 755 /app/output /app/tmp /home/ezrapi/temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TEMP_FOLDER=/home/ezrapi/temp

# Default command shows help
CMD ["python3", "hoopla_main.py", "--help"]