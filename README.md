# hoopla_dl.py

This Python script is used to download audiobooks from Hoopla. It uses the Widevine DRM decryption method to download and decrypt the audiobook files. 

## Python Requirements

The script requires several Python packages to function correctly. These can be installed using pip:

```pip install -r requirements.txt```

The required packages are listed in the requirements.txt file.

## External Dependencies

[FFMPEG](https://ffmpeg.org/download.html) and [mp4decrypt](http://www.bento4.com/downloads/) binary are also required and need to be present in PATH.

mp4decrypt binary can be found in bento4.

[yt-dlp](https://github.com/yt-dlp/yt-dlp#release-files) is used, but I believe the python module have that covered. 

## Usage

The script can be run from the command line with the following syntax:

```python hoopla_dl.py [command] [arguments]```

There are two commands available:

- `list`: Lists all borrowed items.
- `download`: Downloads an item. Requires the ID of the item as an argument.

Example:

```python hoopla_dl.py download 123456```

## Configuration

The script requires a `config.ini` file in the same directory. This file should contain your Hoopla username and password under the [Credentials] section.

```
[Credentials]
username = your_username
password = your_password
```

Limitation: Right now passwords with special symbols does not work, please change your password to not include that if you want to use this script right now

## Note

Widevine CDM might stop working, if the CDM is blocked. You can replace the CDM manually in the widevine_keys/cdm/devices folder

Quality of Hoopla download varies, some are low bitrate, some doesnt have chapters. These are not my problem

## Version Notes

v0.1.0 Initial release

v0.1.1 Fix for titles with no genre

v0.1.2 Fix for folder names with invalid cases for windows 

v0.1.3 Fix album tag is tagged with author, now its tagged with title and subtitle

v0.1.4 Handle synopsis key error, Mark abridged books in output folder, print book name after download completes

## Authors
 - [Joshuatly Tee](https://github.com/joshuatly)

## Credit

[widevine_keys](https://github.com/medvm/widevine_keys) - This code is included an old copy of the code, but edited to make it work with hoopla. 

kabutops728 on MAM - Original HooplaDownloader powershell script
