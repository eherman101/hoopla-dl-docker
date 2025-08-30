import os
import re
import zipfile
import shutil
import base64
import hashlib
import subprocess
from datetime import datetime, timezone
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from urllib.parse import unquote, urlparse
import mutagen.mp4
from mutagen.mp4 import MP4
from widevine_keys.getPSSH import get_pssh
from widevine_keys.l3 import WV_Function

# --- Constants and Configuration ---
HEADERS = {
    'app': 'ANDROID',
    'app-version': '4.53.4',
    'device-module': 'KFKAWI',
    'device-version': '',
    'hoopla-verson': '4.53.4',
    'kids-mode': 'false',
    'os': 'ANDROID',
    'os-version': '6.0.1',
    'ws-api': '2.1',
    'Host': 'patron-api-gateway.hoopladigital.com',
    'User-Agent': 'Hoopla Android/4.27'
}

URL_HOOPLA_WS_BASE = 'https://patron-api-gateway.hoopladigital.com/core'
URL_HOOPLA_LIC_BASE = 'https://patron-api-gateway.hoopladigital.com/license'

COMIC_IMAGE_EXTS = ['.jpg', '.png', '.jpeg', '.gif', '.bmp', '.tif', '.tiff']

class HooplaKind:
    EBOOK = 5
    MUSIC = 6
    MOVIE = 7
    AUDIOBOOK = 8
    TELEVISION = 9
    COMIC = 10

SUPPORTED_KINDS = {HooplaKind.EBOOK, HooplaKind.COMIC, HooplaKind.AUDIOBOOK}

# --- Helper Functions (Replicating PowerShell Functions) ---

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
    url = f"{URL_HOOPLA_WS_BASE}/users"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

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

def invoke_hoopla_zip_download(patron_id, token, circ_id, out_file, media_key):
    """Replicates Invoke-HooplaZipDownload."""
    # Note: The PowerShell script has a commented out URL and a hardcoded new one.
    # We will use the hardcoded one as it seems to be the intended behavior.
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

def get_hoopla_key(patron_id, token, circ_id, media_key):
    """Replicates Get-HooplaKey."""
    # Note: The PowerShell script has a commented out URL and a hardcoded new one.
    # We will use the hardcoded one as it seems to be the intended behavior.
    url = f"{URL_HOOPLA_LIC_BASE}/downloads/book/key/{media_key}"
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    headers['patron-id'] = str(patron_id)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def get_file_key_key(circ_id, due, patron_id, media_key):
    """Replicates Get-FileKeyKey."""
    # Note: The PowerShell script has a commented out and a new method.
    # The new method uses mediaKey twice. We'll follow that.
    combined = f"{media_key}:{patron_id}:{media_key}"
    sha1 = hashlib.sha1(combined.encode('utf-8')).digest()
    return sha1[:16]

def decrypt_file_key(file_key_enc, file_key_key):
    """Replicates Decrypt-FileKey."""
    # This uses ECB mode, which is generally insecure, but it's what the original script does.
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
    # Use the same IV logic as PowerShell: UTF8 bytes of MediaKey, first 16 bytes
    iv = media_key.encode('utf-8')[:16]
    
    cipher = Cipher(algorithms.AES(file_key), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    
    with open(input_filename, 'rb') as infile, open(output_filename, 'wb') as outfile:
        # Decrypt block by block
        while True:
            chunk = infile.read(1024)
            if not chunk:
                break
            outfile.write(decryptor.update(chunk))
        
        outfile.write(decryptor.finalize())

def remove_invalid_filename_chars(name):
    """Replicates Remove-InvalidFileNameChars."""
    # Based on the original script, we replace invalid characters with an underscore.
    # We'll use a regex for this.
    invalid_chars_pattern = r'[<>:"/\\|?*\n]'
    return re.sub(invalid_chars_pattern, '_', name)

def remove_bom_from_file(path, destination):
    """Replicates Remove-BomFromFile function from PowerShell script."""
    # Read content as text (this automatically handles BOM)
    with open(path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # Write without BOM using utf-8 encoding
    with open(destination, 'w', encoding='utf-8') as f:
        f.write(content)

def convert_hoopla_decrypted_to_epub(input_folder, out_folder, epub_zip_bin=None):
    """Replicates Convert-HooplaDecryptedToEpub."""
    import xml.etree.ElementTree as ET
    import subprocess
    from urllib.parse import unquote
    
    try:
        # Read container.xml to find the root file
        container_path = os.path.join(input_folder, 'META-INF', 'container.xml')
        try:
            container_tree = ET.parse(container_path)
        except ET.ParseError as e:
            print(f"Warning: XML parse error in container.xml: {e}. Attempting to fix...")
            # Read and clean the file
            with open(container_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            # Remove any null bytes or other problematic characters
            content = content.replace('\x00', '').replace('\ufffd', '')
            container_tree = ET.fromstring(content)
        root_files = container_tree.findall('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
        root_file = root_files[0].get('full-path')
        
        # Read the content OPF file
        content_file = os.path.join(input_folder, root_file).replace('\\', '/')
        content_root = os.path.dirname(content_file)
        try:
            content_tree = ET.parse(content_file)
        except ET.ParseError as e:
            print(f"Warning: XML parse error in {content_file}: {e}. Attempting to fix...")
            # Read and clean the file
            with open(content_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            # Remove any null bytes or other problematic characters
            content = content.replace('\x00', '').replace('\ufffd', '')
            content_tree = ET.fromstring(content)
        
        # Get file list from manifest
        manifest_items = content_tree.findall('.//{http://www.idpf.org/2007/opf}item')
        file_list = []
        for item in manifest_items:
            href = unquote(item.get('href'))
            file_path = os.path.join(content_root, href).replace('\\', '/').strip()
            file_list.append(file_path)
        
        # Add the content file itself
        file_list.append(content_file)
        file_list = list(set(file_list))  # Remove duplicates
        
        # Extract title and author from metadata
        title_elem = content_tree.find('.//{http://purl.org/dc/elements/1.1/}title')
        title = title_elem.text if title_elem is not None else "Unknown Title"
        
        creator_elem = content_tree.find('.//{http://purl.org/dc/elements/1.1/}creator')
        author = creator_elem.text if creator_elem is not None else "Unknown Author"
        
        # Remove unused files from content root and input folder
        mimetype_file = os.path.join(input_folder, 'mimetype')
        
        # Remove extra files that aren't in the manifest
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                file_path = os.path.join(root, file).replace('\\', '/')
                if file_path not in file_list and file_path != mimetype_file:
                    try:
                        os.remove(file_path)
                    except:
                        pass
        
        # Create container.xml if missing in content root
        content_container_dir = os.path.join(content_root, 'META-INF')
        content_container_path = os.path.join(content_container_dir, 'container.xml')
        if not os.path.exists(content_container_path):
            os.makedirs(content_container_dir, exist_ok=True)
            container_xml = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>

'''
            # Write with UTF-8 encoding (which may include BOM)
            with open(content_container_path, 'w', encoding='utf-8') as f:
                f.write(container_xml)
            
            # Remove BOM like the PowerShell script does
            temp_path = content_container_path + '.tmp'
            remove_bom_from_file(content_container_path, temp_path)
            os.remove(content_container_path)
            os.rename(temp_path, content_container_path)
        
        # Create final filename
        final_file = f"{remove_invalid_filename_chars(title)} - {remove_invalid_filename_chars(author)}.epub"
        final_file_path = os.path.join(out_folder, final_file)
        
        # Use epubzip if available, otherwise use zip
        if epub_zip_bin and os.path.exists(epub_zip_bin):
            # Change to input folder and run epubzip
            original_dir = os.getcwd()
            os.chdir(input_folder)
            try:
                result = subprocess.run([epub_zip_bin, final_file_path], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"Successfully created EPUB using epubzip: {final_file}")
                else:
                    raise Exception(f"epubzip failed: {result.stderr}")
            finally:
                os.chdir(original_dir)
        else:
            # Fallback to zip
            print("Warning: epubzip binary not found. Falling back to `zip` command.")
            try:
                # Create zip archive
                shutil.make_archive(final_file_path[:-5], 'zip', root_dir=input_folder)
                # Rename to .epub
                os.rename(final_file_path[:-5] + '.zip', final_file_path)
                print(f"Successfully created EPUB using internal zip: {final_file}")
            except Exception as e:
                print(f"Error creating EPUB with internal zip: {e}")
                return
        
        return final_file_path
        
    except Exception as e:
        print(f"Error in EPUB conversion: {e}")
        # Fallback to simple zip
        try:
            final_file = f"{remove_invalid_filename_chars(os.path.basename(input_folder))}.epub"
            final_file_path = os.path.join(out_folder, final_file)
            shutil.make_archive(final_file_path[:-5], 'zip', root_dir=input_folder)
            os.rename(final_file_path[:-5] + '.zip', final_file_path)
            print(f"Created fallback EPUB: {final_file}")
            return final_file_path
        except Exception as e2:
            print(f"Fallback EPUB creation also failed: {e2}")
            return

def convert_hoopla_decrypted_to_cbz(input_folder, out_folder, name):
    """Replicates Convert-HooplaDecryptedToCbz."""
    file_name = remove_invalid_filename_chars(name)
    final_out_file = os.path.join(out_folder, f"{file_name}.cbz")
    
    image_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if os.path.splitext(f)[1].lower() in COMIC_IMAGE_EXTS]
    
    with zipfile.ZipFile(final_out_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in image_files:
            zipf.write(file, os.path.basename(file))
            
    return final_out_file

# --- Audiobook Processing Functions ---
def get_x_dt_auth_token_for_audiobook(book_media_key, circ_id, token, patron_id):
    """Get X-DT-Auth-Token for audiobook Widevine DRM."""
    headers = HEADERS.copy()
    headers['Authorization'] = f'Bearer {token}'
    url = f"https://patron-api-gateway.hoopladigital.com/license/castlabs/upfront-auth-tokens/{book_media_key}/{patron_id}/{circ_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.content.decode("utf-8")

def widevine_audiobook(mpd_url, x_dt_auth_token):
    """Get Widevine keys for audiobook."""
    lic_url = "https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true"
    pssh = get_pssh(mpd_url)
    params = urlparse(lic_url).query
    correct, keys = WV_Function(pssh, lic_url, x_dt_auth_token, params=params)
    for key in keys:
        return key

def download_audiobook_mpd(book_media_key, key):
    """Download and decrypt audiobook using yt-dlp and mp4decrypt."""
    temp_dir = "tmp/"
    
    # Ensure temp directory exists
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    mpd_url = f"https://dash.hoopladigital.com/{book_media_key}/Manifest.mpd"
    enc_filename = os.path.join(temp_dir, f"{book_media_key}.enc.m4a")
    dec_filename = os.path.join(temp_dir, f"{book_media_key}.dec.m4a") 
    fixed_filename = os.path.join(temp_dir, f"{book_media_key}.notag.m4b")

    dl_command = ["yt-dlp", "--allow-unplayable-formats", "-o", enc_filename, mpd_url]
    decrypt_command = ["mp4decrypt", "--key", key, enc_filename, dec_filename]
    fix_command = ["ffmpeg", "-i", dec_filename, "-c:a", "copy", fixed_filename]

    try:
        subprocess.run(dl_command, check=True)
        subprocess.run(decrypt_command, check=True) 
        subprocess.run(fix_command, check=True)
    except Exception as e:
        print(f"An error occurred during audiobook download/decryption: {str(e)}")
        raise
    finally:
        if os.path.exists(enc_filename):
            os.remove(enc_filename)
        if os.path.exists(dec_filename):
            os.remove(dec_filename)

def process_audiobook(info, token, patron_id_param):
    """Process audiobook using Widevine DRM workflow."""
    # This uses the same logic as hoopla_audiobooks.py
    contents = info['contents'][0]
    circ_id = contents.get('circId')
    media_key = contents.get('mediaKey')
    
    print(f"Starting audiobook download for: {info['title']}")
    print(f"Media Key: {media_key}, Circ ID: {circ_id}")
    
    # Get auth token and keys
    x_dt_auth_token = get_x_dt_auth_token_for_audiobook(media_key, circ_id, token, patron_id_param)
    mpd_url = f"https://dash.hoopladigital.com/{media_key}/Manifest.mpd"
    decrypt_key = widevine_audiobook(mpd_url, x_dt_auth_token)
    
    # Download and decrypt
    download_audiobook_mpd(media_key, decrypt_key)
    print(f"Audiobook '{info['title']}' processing completed.")

def main():
    """Main script logic."""
    # --- Parameter Parsing and Setup (Simplified) ---
    # In Python, this would typically be done with `argparse`.
    # For this example, we'll hardcode some values or use command-line arguments.
    import argparse

    parser = argparse.ArgumentParser(description="Download and decrypt Hoopla content.")
    parser.add_argument('--username', type=str, help='Hoopla username (or set HOOPLA_USERNAME env var).')
    parser.add_argument('--password', type=str, help='Hoopla password (or set HOOPLA_PASSWORD env var).')
    parser.add_argument('--title-id', type=int, nargs='*', help='Specific title IDs to download.')
    parser.add_argument('--all-borrowed', action='store_true', help='Download all borrowed titles.')
    parser.add_argument('--output-folder', type=str, default=os.getcwd(), help='Output folder for downloaded files.')
    parser.add_argument('--keep-decrypted-data', action='store_true', help='Keep decrypted data in temp folder.')
    parser.add_argument('--keep-encrypted-data', action='store_true', help='Keep encrypted data in temp folder.')
    parser.add_argument('--ffmpeg-bin', type=str, help='Path to ffmpeg binary.')
    parser.add_argument('--epub-zip-bin', type=str, help='Path to epubzip binary.')
    parser.add_argument('--use-existing-download', type=str, help='Use an existing download directory instead of re-downloading.')

    args = parser.parse_args()
    
    output_folder = args.output_folder
    
    if not os.path.exists(output_folder):
        print("Output folder doesn't exist. Creating.")
        os.makedirs(output_folder)

    # Get credentials from args or environment variables
    username = args.username or os.getenv('HOOPLA_USERNAME')
    password = args.password or os.getenv('HOOPLA_PASSWORD')
    
    if not username:
        print("Error: Username required. Use --username or set HOOPLA_USERNAME environment variable.")
        return
    if not password:
        print("Error: Password required. Use --password or set HOOPLA_PASSWORD environment variable.")
        return

    # --- Main Execution Flow ---
    try:
        token = connect_hoopla(username, password)
        print(f"Logged in. Received token: {token}")

        users = get_hoopla_users(token)
        print(f"Found {len(users.get('patrons', []))} patrons")

        user_id = users['id']
        patron_id = users['patrons'][0]['id']
        print(f"Using PatronId {patron_id}")

        borrowed_raw = get_hoopla_borrowed_titles(user_id, patron_id, token)
        # borrowed_raw is already a list, not a dict
        borrowed = [t for t in borrowed_raw if t.get('kind', {}).get('id') in SUPPORTED_KINDS]
        print(f"Found {len(borrowed)} titles already borrowed.")

        to_download = []
        if args.all_borrowed:
            to_download = borrowed
        elif args.title_id:
            to_download = [t for t in borrowed if t['id'] in args.title_id]
            to_borrow = [tid for tid in args.title_id if tid not in [t['id'] for t in borrowed]]

            if to_borrow:
                borrows_remaining_data = get_hoopla_borrows_remaining(user_id, patron_id, token)
                print(borrows_remaining_data.get('borrowsRemainingMessage', ''))
                borrows_remaining = borrows_remaining_data.get('borrowsRemaining')

                for title_id_to_borrow in to_borrow:
                    title_info = get_hoopla_title_info(patron_id, token, title_id_to_borrow)
                    if title_info.get('kind', {}).get('id') in SUPPORTED_KINDS:
                        if borrows_remaining and borrows_remaining <= 0:
                            print(f"Warning: Title {title_id_to_borrow} not borrowed, but we're out of remaining borrows. Skipping...")
                        else:
                            print(f"Borrowing title {title_id_to_borrow}...")
                            res = invoke_hoopla_borrow(user_id, patron_id, token, title_id_to_borrow)
                            print(f"Response: {res.get('message', 'No message')}")
                            new_to_download = [t for t in res.get('titles', []) if t['id'] == title_id_to_borrow]
                            if new_to_download:
                                to_download.extend(new_to_download)
                    else:
                        print(f"Warning: Title {title_id_to_borrow} is not a supported kind. Skipping...")

        temp_folder = os.path.join(os.path.expanduser('~'), 'temp')
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        now = datetime.now().strftime('%Y%m%d%H%M%S')

        for info in to_download:
            # contents is a list, so get the first item
            contents = info['contents'][0]
            circ_id = contents.get('circId')
            media_key = contents.get('mediaKey')
            due_unix = contents.get('due') / 1000
            due_date = datetime.fromtimestamp(due_unix, tz=timezone.utc)
            content_kind = info.get('kind', {}).get('id')
            if contents.get('mediaType'):
                content_kind = contents.get('mediaType')
            
            # Audiobooks use a completely different approach - Widevine DRM streaming
            if content_kind == HooplaKind.AUDIOBOOK:
                print(f"Processing audiobook: {info['title']}")
                process_audiobook(info, token, patron_id)
                continue
                
            # For ebooks and comics, use the ZIP download approach
            enc_dir = os.path.join(temp_folder, f'enc-{circ_id}-{now}')
            dec_dir = os.path.join(temp_folder, f'dec-{circ_id}-{now}')
            
            if not args.use_existing_download:
                circ_file_name = os.path.join(temp_folder, f'{circ_id}.zip')
                invoke_hoopla_zip_download(patron_id, token, circ_id, circ_file_name, media_key)
                
                if not os.path.exists(enc_dir):
                    os.makedirs(enc_dir)
                
                with zipfile.ZipFile(circ_file_name, 'r') as zip_ref:
                    zip_ref.extractall(enc_dir)
                
                os.remove(circ_file_name)
            else:
                enc_dir = args.use_existing_download
            
            key_data = get_hoopla_key(patron_id, token, circ_id, media_key)
            file_key_key = get_file_key_key(circ_id, due_date, patron_id, media_key)
            file_key_enc_bytes = base64.b64decode(key_data)
            file_key = decrypt_file_key(file_key_enc_bytes, file_key_key)
            
            if not os.path.exists(dec_dir):
                os.makedirs(dec_dir)
            
            zip_files = []
            for root, _, files in os.walk(enc_dir):
                for f in files:
                    zip_files.append(os.path.join(root, f))
            
            for i, file_path in enumerate(zip_files):
                relative_path = os.path.relpath(file_path, enc_dir)
                output_path = os.path.join(dec_dir, relative_path)
                
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                if content_kind == HooplaKind.AUDIOBOOK and file_path.endswith('.m3u8'):
                    with open(file_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
                        for line in infile:
                            if not line.startswith('#EXT-X-KEY'):
                                outfile.write(line)
                    continue

                if os.path.getsize(file_path) > 0:
                    try:
                        decrypt_file(file_key, media_key, file_path, output_path)
                    except Exception as e:
                        # As per the original script, some files might be unencrypted.
                        print(f"Failed to decrypt {file_path}. Trying to copy as is. Error: {e}")
                        shutil.copy(file_path, output_path)
                else:
                    with open(output_path, 'w') as f:
                        f.write('')
            
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
                print(f"Decrypted data for {info['id']} ({info['title']}) stored in {dec_dir}")
                
            if not args.keep_encrypted_data:
                shutil.rmtree(enc_dir)

    except requests.exceptions.RequestException as e:
        print(f"An HTTP request error occurred: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()