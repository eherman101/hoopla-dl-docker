import os
import re
import zipfile
import shutil
import base64
import hashlib
from datetime import datetime, timezone
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from urllib.parse import unquote
import subprocess
import yt_dlp
import json
import configparser
import urllib.parse
import argparse
import mutagen.mp4
from mutagen.mp4 import MP4
from widevine_keys.getPSSH import get_pssh
from widevine_keys.l3 import WV_Function
from urllib.parse import urlparse

# --- Constants and Configuration from both scripts ---
USER_AGENT = 'Hoopla Android/4.27'
HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://www.hoopladigital.com',
    'Pragma': 'no-cache',
    'Referer': 'https://www.hoopladigital.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': USER_AGENT,
    'app': 'ANDROID',
    'app-version': '4.53.4',
    'device-module': 'KFKAWI',
    'device-version': '',
    'hoopla-verson': '4.53.4',
    'kids-mode': 'false',
    'os': 'ANDROID',
    'os-version': '6.0.1',
    'ws-api': '2.1',
    'Host': 'patron-api-gateway.hoopladigital.com'
}

URL_HOOPLA_WS_BASE = 'https://patron-api-gateway.hoopladigital.com/core'
URL_HOOPLA_LIC_BASE = 'https://patron-api-gateway.hoopladigital.com/license'

COMIC_IMAGE_EXTS = ['.jpg', '.png', '.jpeg', '.gif', '.bmp', '.tif', '.tiff']

output_dir = "output/"
temp_dir = "tmp/"
chapter_output = "tmp/chapters.txt"

class HooplaKind:
    EBOOK = 5
    MUSIC = 6
    MOVIE = 7
    AUDIOBOOK = 8
    TELEVISION = 9
    COMIC = 10

SUPPORTED_KINDS = {HooplaKind.EBOOK, HooplaKind.COMIC, HooplaKind.AUDIOBOOK}

# Declare global variables to store authToken and patron_id
authToken = None
user_id = None
patron_id = None

# --- Helper Functions from hoopla_main.py ---
def connect_hoopla(username, password):
    """Replicates Connect-Hoopla."""
    url = f"{URL_HOOPLA_WS_BASE}/tokens"
    body = {'username': username, 'password': password}
    response = requests.post(url, headers=HEADERS, data=body)
    response.raise_for_status()
    data = response.json()
    if data.get('tokenStatus') != 'SUCCESS':
        raise Exception(data.get('message', 'Failed to get token'))
    return data['token']

def get_hoopla_users(token):
    """Replicates Get-HooplaUsers."""
    global authToken, user_id, patron_id
    url = f"{URL_HOOPLA_WS_BASE}/users"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    response_data = response.json()
    
    # Update global variables
    authToken = token
    user_id = response_data.get('id')
    patron_id = response_data.get('patrons', [{}])[0].get('id')

    return response_data

def get_hoopla_title_info(patron_id, token, title_id):
    """Replicates Get-HooplaTitleInfo."""
    url = f"{URL_HOOPLA_WS_BASE}/v2/titles/{title_id}"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    headers['patron-id'] = str(patron_id)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_hoopla_borrows_remaining(user_id, patron_id, token):
    """Replicates Get-HooplaBorrowsRemaining."""
    url = f"{URL_HOOPLA_WS_BASE}/users/{user_id}/patrons/{patron_id}/borrows-remaining"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    headers['patron-id'] = str(patron_id)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_hoopla_borrowed_titles(user_id, patron_id, token):
    """Replicates Get-HooplaBorrowedTitles."""
    url = f"{URL_HOOPLA_WS_BASE}/users/{user_id}/borrowed-titles"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    headers['patron-id'] = str(patron_id)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def invoke_hoopla_borrow(user_id, patron_id, token, title_id):
    """Replicates Invoke-HooplaBorrow."""
    url = f"{URL_HOOPLA_WS_BASE}/users/{user_id}/patrons/{patron_id}/borrowed-titles/{title_id}"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    headers['patron-id'] = str(patron_id)
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()

def invoke_hoopla_zip_download(patron_id, token, out_file, media_key):
    """Replicates Invoke-HooplaZipDownload."""
    url = f"{URL_HOOPLA_WS_BASE}/v2/patrons/downloads/{media_key}/url"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    headers['patron-id'] = str(patron_id)
    response = requests.get(url, headers=headers, allow_redirects=False)
    response.raise_for_status()
    
    redirect_url = response.headers.get('Location')
    if not redirect_url:
        raise Exception("Redirect URL not found in response headers.")
    
    download_response = requests.get(redirect_url, stream=True)
    download_response.raise_for_status()
    
    with open(out_file, 'wb') as f:
        for chunk in download_response.iter_content(chunk_size=8192):
            f.write(chunk)

def get_hoopla_key(patron_id, token, media_key):
    """Replicates Get-HooplaKey."""
    url = f"{URL_HOOPLA_LIC_BASE}/downloads/book/key/{media_key}"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    headers['patron-id'] = str(patron_id)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def get_file_key_key(patron_id, media_key):
    """Replicates Get-FileKeyKey."""
    combined = f"{media_key}:{patron_id}:{media_key}"
    sha1 = hashlib.sha1(combined.encode('utf-8')).digest()
    return sha1[:16]

def decrypt_file_key(file_key_enc, file_key_key):
    """Replicates Decrypt-FileKey."""
    backend = default_backend()
    cipher = Cipher(algorithms.AES(file_key_key), modes.ECB(), backend=backend)
    decryptor = cipher.decryptor()
    unpadded_data = decryptor.update(file_key_enc) + decryptor.finalize()
    
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    unencrypted_data = unpadder.update(unpadded_data) + unpadder.finalize()
    
    return unencrypted_data

def decrypt_file(file_key, media_key, input_filename, output_filename):
    """Replicates Decrypt-File."""
    backend = default_backend()
    iv = hashlib.sha1(media_key.encode('utf-8')).digest()[:16]
    
    cipher = Cipher(algorithms.AES(file_key), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    
    with open(input_filename, 'rb') as infile, open(output_filename, 'wb') as outfile:
        while True:
            chunk = infile.read(1024)
            if not chunk:
                break
            outfile.write(decryptor.update(chunk))
        outfile.write(decryptor.finalize())

def remove_invalid_filename_chars(name):
    """Replicates Remove-InvalidFileNameChars."""
    invalid_chars_pattern = r'[<>:"/\\|?*\n]'
    return re.sub(invalid_chars_pattern, '_', name)

def convert_hoopla_decrypted_to_epub(input_folder, out_folder, epub_zip_bin=None):
    """Replicates Convert-HooplaDecryptedToEpub."""
    print("This function requires an external tool and is not fully implemented.")

def convert_hoopla_decrypted_to_cbz(input_folder, out_folder, name):
    """Replicates Convert-HooplaDecryptedToCbz."""
    file_name = remove_invalid_filename_chars(name)
    final_out_file = os.path.join(out_folder, f"{file_name}.cbz")
    
    image_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if os.path.splitext(f)[1].lower() in COMIC_IMAGE_EXTS]
    
    with zipfile.ZipFile(final_out_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in image_files:
            zipf.write(file, os.path.basename(file))
            
    return final_out_file

# --- Helper Functions from hoopla_audiobooks.py ---
def get_x_dt_auth_token(book_mediaKey, circId):
    h = HEADERS.copy()
    h['Authorization'] = f'Bearer {authToken}'
    url = f"{URL_HOOPLA_LIC_BASE}/castlabs/upfront-auth-tokens/{book_mediaKey}/{patron_id}/{circId}"
    response = requests.get(url, headers=h)
    response.raise_for_status()
    return response.content.decode("utf-8")

def widevine(mpd_url, x_dt_auth_token):
    lic_url = "https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true"
    pssh = get_pssh(mpd_url)
    params = urlparse(lic_url).query
    correct, keys = WV_Function(pssh, lic_url, x_dt_auth_token, params=params)
    for key in keys:
        return key

def download_mpd(book_mediaKey, key):
    enc_filename = temp_dir + book_mediaKey + ".encrypted.m4a"
    dec_filename = temp_dir + book_mediaKey + ".decrypted.m4a"
    fixed_filename = temp_dir + book_mediaKey + ".notag.m4b"
    mpd_location = "https://dash.hoopladigital.com/" + book_mediaKey + "/Manifest.mpd"

    dl_command = ["yt-dlp", "--allow-unplayable-formats", "-o", f"{enc_filename}", mpd_location]
    decrypt_command = ["mp4decrypt", "--key", f"{key}", f"{enc_filename}", f"{dec_filename}"]
    fix_command = ["ffmpeg", "-i", f"{dec_filename}", "-c:a", "copy", f"{fixed_filename}"]

    try:
        subprocess.run(dl_command, check=True)
        subprocess.run(decrypt_command, check=True)
        subprocess.run(fix_command, check=True)
    except Exception as e:
        print(f"An error occurred during download/decryption: {str(e)}")
        raise
    finally:
        if os.path.exists(enc_filename):
            os.remove(enc_filename)
        if os.path.exists(dec_filename):
            os.remove(dec_filename)

def download_cover(book_mediaKey):
    cover_small_url = f"http://d2snwnmzyr8jue.cloudfront.net/{book_mediaKey}_540.jpeg"
    cover_big_url = f"http://d2snwnmzyr8jue.cloudfront.net/{book_mediaKey}_1080.jpeg"
    try:
        response_small = requests.get(cover_small_url)
        response_small.raise_for_status()
        with open(os.path.join(temp_dir, "cover.tag.jpg"), 'wb') as f:
            f.write(response_small.content)

        response_big = requests.get(cover_big_url)
        response_big.raise_for_status()
        with open(os.path.join(temp_dir, "cover.jpg"), 'wb') as f:
            f.write(response_big.content)
    except Exception as e:
        print(f"Error downloading cover: {str(e)}")

def get_title_json(title_id):
    api_url = f"https://patron-api-gateway.hoopladigital.com/core/titles/{title_id}"
    try:
        h = HEADERS.copy()
        h['Authorization'] = f'Bearer {authToken}'
        response = requests.get(api_url, headers=h)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")
        return None

def escape_metadata(data):
    return re.sub(r'([\\=;#\n])', r'\\\1', data)

def gen_ffmpeg_chapter(input_json):
    try:
        metadata_file_content = ';FFMETADATA1\n'
        for chapter in input_json["contents"][0]["chapters"]:
            metadata_file_content += '[CHAPTER]\nTIMEBASE=1/1000\n'
            metadata_file_content += 'START=%d\n' % (chapter['start'] * 1000)
            if 'end' in chapter:
                end_time = chapter['end'] * 1000
            else:
                end_time = (chapter['start'] + chapter['duration']) * 1000
            metadata_file_content += 'END=%d\n' % end_time
            chapter_title = chapter["title"]
            if chapter_title:
                metadata_file_content += 'title=%s\n' % escape_metadata(chapter_title)

        with open(chapter_output, "w") as output_file:
            output_file.write(metadata_file_content)
    except Exception as e:
        print(f"Error generating chapters.txt: {e}")
        raise

def ffmpeg_tag_chapter(book_mediaKey):
    fixed_filename = temp_dir + book_mediaKey + ".notag.m4b"
    chapter_tagged = temp_dir + book_mediaKey + ".m4b"
    cmd = [
        "ffmpeg",
        "-i", fixed_filename,
        "-i", chapter_output,
        "-map_metadata", "1",
        "-acodec", "copy",
        chapter_tagged
    ]
    try:
        subprocess.run(cmd, check=True)
        os.remove(fixed_filename)
        os.remove(chapter_output)
    except Exception as e:
        print(f"Error tagging m4b file with chapter.txt: {str(e)}")
        raise

def tag_mutagen(input_json):
    try:
        authors = [artist["name"] for artist in input_json.get("artists", []) if artist["relationship"] == "AUTHOR"]
        readers = [artist["name"] for artist in input_json.get("artists", []) if artist["relationship"] == "READER"]
        book_mediaKey = input_json['contents'][0]['mediaKey']
        first_content = input_json['contents'][0]
        title = first_content.get('title', '')
        subtitle = first_content.get('subtitle')

        publishing_date_timestamp = input_json.get("releaseDate", 0) / 1000
        publishing_date = datetime.utcfromtimestamp(publishing_date_timestamp).strftime("%Y-%m-%dT%H:%M:%S")

        album_value = f"{title} - {subtitle}" if subtitle else title
        metadata_json = {
            "\xa9nam": input_json.get("title", ""),
            "\xa9alb": album_value,
            "\xa9ART": ", ".join(authors),
            "\xa9wrt": ", ".join(readers),
            "cprt": f"©{input_json.get('year', '')} {input_json.get('publisher', {}).get('name', '')}",
            "\xa9nrt": ", ".join(readers),
            "\xa9pub": input_json.get("publisher", {}).get("name", ""),
            "\xa9day": publishing_date
        }

        if 'genres' in input_json and isinstance(input_json["genres"], list) and input_json["genres"]:
            metadata_json["\xa9gen"] = input_json["genres"][0]["name"]
        
        if 'synopsis' in input_json and input_json["synopsis"]:
            metadata_json["desc"] = input_json["synopsis"]
            metadata_json["\xa9cmt"] = input_json["synopsis"]

        download_cover(book_mediaKey)
        file_path = temp_dir + book_mediaKey + ".m4b"
        audio = mutagen.mp4.MP4(file_path)

        for key, value in metadata_json.items():
            audio[key] = [value]

        cover_image_path = os.path.join(temp_dir, "cover.tag.jpg")
        audio['covr'] = [mutagen.mp4.MP4Cover(open(cover_image_path, 'rb').read(), imageformat=mutagen.mp4.MP4Cover.FORMAT_JPEG)]
        audio.save()
        if os.path.exists(cover_image_path):
            os.remove(cover_image_path)
    except Exception as ve:
        print(f"Error writing metadata file to m4b: {ve}")
        raise

def move_and_rename_m4b(input_json):
    authors = [artist["name"] for artist in input_json.get("artists", []) if artist["relationship"] == "AUTHOR"]
    book_author = ", ".join(authors)
    book_title = input_json.get("title", "")
    
    try:
        book_title = re.sub(r"([\\/:*?\"<>|])", r"", book_title)
        book_author = re.sub(r"([\\/:*?\"<>|])", r"", book_author)
        abridged = input_json.get("abridged", False)

        final_dir = os.path.join(output_dir, f"{book_title} - {book_author}")
        if abridged:
            final_dir += " [Abridged]"
        os.makedirs(final_dir, exist_ok=True)

        files_to_move = os.listdir(temp_dir)
        renamed_m4b = None
        for file_to_move in files_to_move:
            source_file_path = os.path.join(temp_dir, file_to_move)
            if file_to_move.endswith(".m4b"):
                renamed_m4b = os.path.join(final_dir, f"{book_title}.m4b")
                shutil.move(source_file_path, renamed_m4b)
                mp4 = MP4(renamed_m4b)
                bitrate = mp4.info.bitrate
            else:
                shutil.move(source_file_path, final_dir)

        if renamed_m4b:
            print(f"Downloaded {book_title} - {book_author}")
            print(f"Audiobook processing finished.\nBitrate: {bitrate / 1000} kbps")
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def process_audiobook(item):
    """Handles the full audiobook download and processing workflow."""
    global patron_id
    if not patron_id:
        print("Patron ID not set. Cannot process audiobook.")
        return

    # Ensure temp directory is clean before starting
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    contents = item.get('contents', [{}])[0]
    circ_id = contents.get('circId')
    book_mediaKey = contents.get('mediaKey')
    title_id = item['id']

    # Get x_dt_auth_token
    x_dt_auth_token = get_x_dt_auth_token(book_mediaKey, circ_id)
    
    # Get decryption key
    mpd_url = f"https://dash.hoopladigital.com/{book_mediaKey}/Manifest.mpd"
    decrypt_key = widevine(mpd_url, x_dt_auth_token)

    # Download and decrypt MPD
    download_mpd(book_mediaKey, decrypt_key)
    
    # Get title metadata for chapters and tags
    book_json = get_title_json(title_id)
    
    # Generate and tag chapters
    gen_ffmpeg_chapter(book_json)
    ffmpeg_tag_chapter(book_mediaKey)
    
    # Tag metadata with mutagen
    tag_mutagen(book_json)
    
    # Move and rename files
    move_and_rename_m4b(book_json)

# --- Main Script Logic ---
def main():
    parser = argparse.ArgumentParser(description="Download and decrypt Hoopla content.")
    parser.add_argument('--username', type=str, help='Hoopla username.')
    parser.add_argument('--password', type=str, help='Hoopla password.')
    parser.add_argument('--title-id', type=int, nargs='*', help='Specific title IDs to download.')
    parser.add_argument('--all-borrowed', action='store_true', help='Download all borrowed titles.')
    parser.add_argument('--output-folder', type=str, default=output_dir, help='Output folder for downloaded files.')
    parser.add_argument('--keep-decrypted-data', action='store_true', help='Keep decrypted data in temp folder.')
    parser.add_argument('--keep-encrypted-data', action='store_true', help='Keep encrypted data in temp folder.')
    parser.add_argument('--ffmpeg-bin', type=str, help='Path to ffmpeg binary.')
    parser.add_argument('--epub-zip-bin', type=str, help='Path to epubzip binary.')
    parser.add_argument('--use-existing-download', type=str, help='Use an existing download directory instead of re-downloading.')
    parser.add_argument('--config-file', type=str, default='config.ini', help='Path to config.ini file for credentials.')

    args = parser.parse_args()

    # Get credentials from command line or config file
    if args.username and args.password:
        username = args.username
        password = args.password
    else:
        config = configparser.ConfigParser()
        if not os.path.exists(args.config_file):
            print("Error: No credentials provided and config.ini file not found.")
            return
        config.read(args.config_file)
        username = config['Credentials']['username']
        password = config['Credentials']['password']

    # Check and create output folder
    output_folder = args.output_folder
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Main Execution Flow
    try:
        token = connect_hoopla(username, password)
        print(f"Logged in. Received token: {token}")

        users = get_hoopla_users(token)
        print(f"Found {len(users.get('patrons', []))} patrons")
        
        # Get borrowed titles
        borrowed_raw = get_hoopla_borrowed_titles(user_id, patron_id, token)
        borrowed = [t for t in borrowed_raw if t.get('kind', {}).get('id') in SUPPORTED_KINDS]
        print(f"Found {len(borrowed)} supported titles already borrowed.")

        to_download = []
        if args.all_borrowed:
            to_download = borrowed
        elif args.title_id:
            to_download = [t for t in borrowed if t['id'] in args.title_id]
            to_borrow = [tid for tid in args.title_id if tid not in [t['id'] for t in borrowed]]
            
            if to_borrow:
                borrows_remaining_data = get_hoopla_borrows_remaining(user_id, patron_id, token)
                borrows_remaining = borrows_remaining_data.get('borrowsRemaining')
                for title_id_to_borrow in to_borrow:
                    title_info = get_hoopla_title_info(patron_id, token, title_id_to_borrow)
                    if title_info.get('kind', {}).get('id') in SUPPORTED_KINDS:
                        if borrows_remaining and borrows_remaining <= 0:
                            print(f"Warning: Title {title_id_to_borrow} not borrowed, but we're out of remaining borrows. Skipping...")
                        else:
                            print(f"Borrowing title {title_id_to_borrow}...")
                            res = invoke_hoopla_borrow(user_id, patron_id, token, title_id_to_borrow)
                            new_to_download = [t for t in res.get('titles', []) if t['id'] == title_id_to_borrow]
                            if new_to_download:
                                to_download.extend(new_to_download)
                    else:
                        print(f"Warning: Title {title_id_to_borrow} is not a supported kind. Skipping...")

        now = datetime.now().strftime('%Y%m%d%H%M%S')
        
        for item in to_download:
            content_kind = item.get('kind', {}).get('id')
            if content_kind == HooplaKind.AUDIOBOOK:
                process_audiobook(item)
                continue
            
            # Continue with existing logic for ebooks/comics
            contents = item['contents']
            circ_id = contents.get('circId')
            media_key = contents.get('mediaKey')
            
            enc_dir = os.path.join(temp_dir, f'enc-{circ_id}-{now}')
            dec_dir = os.path.join(temp_dir, f'dec-{circ_id}-{now}')
            
            if not args.use_existing_download:
                circ_file_name = os.path.join(temp_dir, f'{circ_id}.zip')
                invoke_hoopla_zip_download(patron_id, token, circ_file_name, media_key)
                
                if not os.path.exists(enc_dir):
                    os.makedirs(enc_dir)
                
                with zipfile.ZipFile(circ_file_name, 'r') as zip_ref:
                    zip_ref.extractall(enc_dir)
                os.remove(circ_file_name)
            else:
                enc_dir = args.use_existing_download
            
            key_data = get_hoopla_key(patron_id, token, media_key)
            file_key_key = get_file_key_key(patron_id, media_key)
            file_key_enc_bytes = base64.b64decode(key_data)
            file_key = decrypt_file_key(file_key_enc_bytes, file_key_key)
            
            if not os.path.exists(dec_dir):
                os.makedirs(dec_dir)
            
            for root, _, files in os.walk(enc_dir):
                for f in files:
                    file_path = os.path.join(root, f)
                    relative_path = os.path.relpath(file_path, enc_dir)
                    output_path = os.path.join(dec_dir, relative_path)
                    
                    output_dir_path = os.path.dirname(output_path)
                    if not os.path.exists(output_dir_path):
                        os.makedirs(output_dir_path)
                    
                    if os.path.getsize(file_path) > 0:
                        try:
                            decrypt_file(file_key, media_key, file_path, output_path)
                        except Exception as e:
                            print(f"Failed to decrypt {file_path}. Trying to copy as is. Error: {e}")
                            shutil.copy(file_path, output_path)
                    else:
                        with open(output_path, 'w') as out_file:
                            out_file.write('')
            
            if content_kind == HooplaKind.EBOOK:
                convert_hoopla_decrypted_to_epub(dec_dir, output_folder, args.epub_zip_bin)
            elif content_kind == HooplaKind.COMIC:
                title = contents.get('title')
                subtitle = contents.get('subtitle')
                name = title
                if subtitle:
                    name += f", {subtitle}"
                convert_hoopla_decrypted_to_cbz(dec_dir, output_folder, name)
            
            if not args.keep_decrypted_data:
                shutil.rmtree(dec_dir)
            else:
                print(f"Decrypted data for {item['id']} ({item['title']}) stored in {dec_dir}")
            
            if not args.keep_encrypted_data:
                shutil.rmtree(enc_dir)

    except requests.exceptions.RequestException as e:
        print(f"An HTTP request error occurred: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()