# Main application container
FROM debian:bookworm-slim

# Install Python and system dependencies including required libraries
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    wget \
    curl \
    gnupg2 \
    ca-certificates \
    libc6 \
    libgcc-s1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*


# Install older bento4 version compatible with bookworm
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
COPY . .

# Create necessary directories
RUN mkdir -p output tmp

# Make the script executable
RUN chmod +x hoopla_dl.py

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python3", "hoopla_dl.py", "--help"]