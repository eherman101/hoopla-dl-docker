# Hoopla-DL Docker

This project containerizes the hoopla_dl.py script for downloading audiobooks from Hoopla Digital library service using Docker.

## Docker Setup

### Prerequisites
- Docker and Docker Compose installed
- Hoopla Digital library account with borrowed audiobooks

### Configuration
1. Copy the example configuration:
   ```bash
   cp config.ini.example config.ini
   ```

2. Edit `config.ini` with your Hoopla credentials:
   ```ini
   [Credentials]
   username = your_username
   password = your_password
   ```

### Usage

**List borrowed audiobooks:**
```bash
docker compose run --rm hoopla-dl python3 hoopla_dl.py list
```

**Download an audiobook:**
```bash
docker compose run --rm hoopla-dl python3 hoopla_dl.py download [ID]
```

**Examples:**
```bash
# List all borrowed books
docker compose run --rm hoopla-dl python3 hoopla_dl.py list

# Download a specific book by ID
docker compose run --rm hoopla-dl python3 hoopla_dl.py download 12411610
```

## Architecture

### Docker Components
- **Base Image**: Debian bookworm-slim (ARM64 compatible)
- **Python Environment**: Python 3.11 with required packages
- **Dependencies**: 
  - ffmpeg for audio processing
  - bento4 (v1.6.0.640) for DRM decryption with mp4decrypt
  - All Python packages from requirements.txt

### Volume Mounts
- `./config.ini:/app/config.ini:ro` - Configuration file (read-only)
- `./output:/app/output` - Downloaded audiobooks output directory
- `./tmp:/app/tmp` - Temporary files during processing
- `./token.json:/app/token.json` - Authentication token cache

### Bento4 Installation
The container uses the older bento4 version (1.6.0.640) from deb-multimedia.org that's compatible with Debian bookworm's libc6 version. This provides the essential mp4decrypt binary for Widevine DRM decryption.

## Files Structure
```
hoopla-dl-docker/
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore           # Docker build exclusions
├── hoopla_dl.py            # Main application script
├── requirements.txt        # Python dependencies
├── config.ini.example      # Configuration template
├── widevine_keys/          # DRM decryption modules
├── output/                 # Downloaded audiobooks
└── tmp/                    # Temporary files
```

## Technical Notes

### DRM Decryption
This application uses Widevine L3 decryption to download protected content from Hoopla. The included Widevine CDM (Content Decryption Module) may need periodic updates if blocked by the service.

### ARM64 Compatibility
The Docker setup is specifically configured for ARM64 architecture (Apple Silicon, Raspberry Pi 4/5) with proper dependency resolution for the target platform.

### Limitations
- Passwords with special symbols may not work (change password if needed)
- Download quality varies by Hoopla's source material
- Some audiobooks may lack proper chapter information

## Troubleshooting

**Build fails with libc6 version conflicts:**
- The Dockerfile uses the compatible bento4 version (1.6.0.640) for bookworm
- Ensure Docker has sufficient memory allocated for the build process

**Authentication issues:**
- Verify credentials in config.ini
- Check that your Hoopla account has active loans
- Delete token.json to force re-authentication

**Missing mp4decrypt:**
- The container should include mp4decrypt from bento4
- Verify with: `docker compose run --rm hoopla-dl which mp4decrypt`

## Legal Notice
This tool is for educational and research purposes only. Users must have valid Hoopla library accounts and should only download content they have legitimately borrowed. Respect copyright laws and terms of service.