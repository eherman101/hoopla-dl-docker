# Hoopla-DL Docker

This project containerizes the hoopla_dl.py script for downloading audiobooks from Hoopla Digital library service using Docker.

## Docker Setup

### Prerequisites
- Docker and Docker Compose installed
- Hoopla Digital library account with borrowed audiobooks

### Configuration
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Hoopla credentials:
   ```bash
   HOOPLA_USERNAME=your_username
   HOOPLA_PASSWORD=your_password
   ```

### Usage

The unified `hoopla_main.py` script supports downloading all content types: **ebooks (EPUB)**, **comics (CBZ)**, and **audiobooks (M4B)**.

**Download specific content by ID:**
```bash
docker compose run --rm hoopla-dl python3 hoopla_main.py --title-id [ID]
```

**Download multiple items:**
```bash
docker compose run --rm hoopla-dl python3 hoopla_main.py --title-id 12360547 12411610 18630080
```

**Download all borrowed content:**
```bash
docker compose run --rm hoopla-dl python3 hoopla_main.py --all-borrowed
```

**Examples by content type:**
```bash
# Download an ebook (EPUB)
docker compose run --rm hoopla-dl python3 hoopla_main.py --title-id 12360547

# Download a comic book (CBZ)
docker compose run --rm hoopla-dl python3 hoopla_main.py --title-id 18630080

# Download an audiobook (M4B)
docker compose run --rm hoopla-dl python3 hoopla_main.py --title-id 12411610

# Keep temporary files for debugging
docker compose run --rm hoopla-dl python3 hoopla_main.py --title-id 12360547 --keep-decrypted-data
```

## Architecture

### Docker Components
- **Base Image**: Debian bookworm-slim (ARM64 compatible)
- **Python Environment**: Python 3.11 with required packages
- **Main Script**: `hoopla_main.py` - Unified downloader for all content types
- **Dependencies**: 
  - **yt-dlp** for audiobook streaming downloads
  - **ffmpeg** for audio/video processing
  - **bento4** (v1.6.0.640) for Widevine DRM decryption (mp4decrypt)
  - **Python packages** from requirements.txt (cryptography, requests, mutagen, etc.)

### Volume Mounts
- `./output:/app/output` - Downloaded content output directory (ebooks, comics, audiobooks)
- `./tmp:/app/tmp` - Temporary files during processing 
- `./tmp:/home/ezrapi/temp` - Additional temp directory for decryption
- `./token.json:/app/token.json` - Authentication token cache (optional)

### Environment Variables
- `HOOPLA_USERNAME` - Your Hoopla Digital username (from .env file)
- `HOOPLA_PASSWORD` - Your Hoopla Digital password (from .env file)
- `OUTPUT_DIR` - Custom output directory (optional)
- `KEEP_DECRYPTED_DATA` - Keep decrypted temporary files (optional)
- `KEEP_ENCRYPTED_DATA` - Keep encrypted temporary files (optional)

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

### Content Type Support
- **📖 EPUB (Ebooks)**: ZIP download → decryption → XML parsing → EPUB generation with metadata
- **🖼️ CBZ (Comics)**: ZIP download → decryption → image compilation → CBZ archive
- **🎧 M4B (Audiobooks)**: Widevine DRM streaming → yt-dlp download → mp4decrypt → ffmpeg conversion

### DRM Decryption
- **Ebooks & Comics**: AES-CBC decryption using patron-specific keys
- **Audiobooks**: Widevine L3 decryption with streaming manifests (MPD files)
- The included Widevine CDM (Content Decryption Module) may need periodic updates if blocked by the service

### ARM64 Compatibility
The Docker setup is specifically configured for ARM64 architecture (Apple Silicon, Raspberry Pi 4/5) with proper dependency resolution for the target platform.

### Limitations
- Passwords with special symbols may not work (change password if needed)  
- Download quality varies by Hoopla's source material
- Some audiobooks may lack proper chapter information
- Content must be actively borrowed from your library account

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
- the ebook and comic book logic and API are based on hoopla_dl.ps1 (known working); the audiobook downloading is based on hoopla_audiobooks.py (known working).