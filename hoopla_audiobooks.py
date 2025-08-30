#!/usr/bin/env python3

import requests
import subprocess
import os
import yt_dlp
import json
import configparser
import urllib.parse
import argparse
import shutil
import mutagen.mp4 
import re

from mutagen.mp4 import MP4
from widevine_keys.getPSSH import get_pssh
from widevine_keys.l3 import WV_Function
from urllib.parse import urlparse
from datetime import datetime

headers = {
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
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
  'app': 'WWW',
  'binge-pass-external-enabled': 'true',
  'binge-pass-internal-enabled': 'undefined',
  'device-model': '116.0.0.0',
  'device-version': 'Chrome',
  'hoopla-version': '4.83.0',
  'os': 'Mac OS',
  'os-version': '10.15.7',
  'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
  'sec-ch-ua-mobile': '?0',
  'sec-ch-ua-platform': '"macOS"',
  'ws-api': '2.1'
}


URL_HOOPLA_WS_BASE = 'https://patron-api-gateway.hoopladigital.com/core/'
URL_HOOPLA_LIC_BASE = 'https://hoopla-license2.hoopladigital.com'

output_dir = "output/"
temp_dir = "tmp/"
chapter_output = "tmp/chapters.txt"

# Declare global variables to store authToken and patrons[id]
authToken = None
user_id = None
patron_id = None


def connect_hoopla():
    if os.path.exists('token.json'):
        with open('token.json', 'r') as token_file:
            token_data = json.load(token_file)
            token = token_data.get('authToken')
            user_data = get_hoopla_users(token)
            if user_data:
                return True
            else:
                os.remove('token.json')
                print("Invalid token removed, please try again")

    config = configparser.ConfigParser()
    config.read('config.ini')

    username = config['Credentials']['username']
    password = config['Credentials']['password']

    # Encode the username for the payload
    encoded_username = urllib.parse.quote(username, safe='')
    encoded_password = urllib.parse.quote(password, safe='')
    
    payload = f'username={encoded_username}&password={encoded_password}'
    url = "https://patron-api-gateway.hoopladigital.com/core/tokens"

    response = requests.request("POST", url, headers=headers, data=payload)
    
    res_json = response.json()

    if res_json['tokenStatus'] != 'SUCCESS':
        print("Credential in config.ini is incorrect. Please check.")
        raise Exception(res_json['message'])
    get_hoopla_users(res_json['token'])
    return True

def get_hoopla_users(token):
    global authToken
    global user_id
    global patron_id

    h = headers.copy()
    h['Authorization'] = f'Bearer {token}'
    url = "https://patron-api-gateway.hoopladigital.com/core/users"
    response = requests.get(url, headers=h)
    
    if response.status_code == 200:
        response_data = response.json()

        with open("token.json", "w") as token_file:
            json.dump(response_data, indent=4, fp=token_file)
        authToken = token
        user_id = response_data.get('id')
        patron_id = response_data.get('patrons', {})[0].get('id')
        return True

    return False


def get_hoopla_borrowed_titles(user_id, patron_id, token):
    h = headers.copy()
    h['Authorization'] = f'Bearer {token}'
    h['patron-id'] = str(patron_id)
    
    url = f"https://patron-api-gateway.hoopladigital.com/core/users/{user_id}/borrowed-titles"
    response = requests.get(url, headers=h)
    return response.json()

# List by ID, need to be in your loaned list
# This function is duplicated by the check if in loan function below
def get_hoopla_item_by_id(book_id):
    borrowed_items = get_hoopla_borrowed_titles(user_id, patron_id, authToken)
    for item in borrowed_items:
        if item['id'] == book_id:
            return item['contents'][0]
    return None

def extract_id_from_url(url):
    # Use regular expressions to find the ID in the URL
    match = re.search(r'/(\d+)(?:\?|$)', url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid URL format")

def get_x_dt_auth_token(book_mediaKey ,circId):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5', 
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'DNT': '1',
        'Origin': 'https://www.hoopladigital.com',
        'Pragma': 'no-cache',
        'Referer': 'https://www.hoopladigital.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'binge-pass-external-enabled': 'undefined',
        'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    headers['Authorization'] = f'Bearer {authToken}'
    
    url = f"https://patron-api-gateway.hoopladigital.com/license/castlabs/upfront-auth-tokens/{book_mediaKey}/{patron_id}/{circId}"
    response = requests.get(url, headers=headers)
    x_dt_auth_token = response.content.decode("utf-8")
    return x_dt_auth_token

def widevine(mpd_url, x_dt_auth_token):
    lic_url = "https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true"

    pssh = get_pssh(mpd_url)
    params = urlparse(lic_url).query

    # print(f'{chr(10)}PSSH obtained.\n{pssh}')
    correct, keys = WV_Function(pssh, lic_url, x_dt_auth_token, params=params)

    for key in keys:
        #print(f'KID:KEY found: {key}')
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
        subprocess.Popen(dl_command).wait()
        subprocess.Popen(decrypt_command).wait()
        subprocess.Popen(fix_command).wait()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Clean up: Delete the enc_filename and dec_filename files
        if os.path.exists(enc_filename):
            os.remove(enc_filename)
        if os.path.exists(dec_filename):
            os.remove(dec_filename)


def download_cover(book_mediaKey):
    cover_small_url = f"http://d2snwnmzyr8jue.cloudfront.net/{book_mediaKey}_540.jpeg"
    cover_big_url = f"http://d2snwnmzyr8jue.cloudfront.net/{book_mediaKey}_1080.jpeg"
    try:
        # Download and save cover_small as "tmp/cover.tag.jpg"
        response_small = requests.get(cover_small_url)
        response_small.raise_for_status()
        
        with open(os.path.join("tmp", "cover.tag.jpg"), 'wb') as f:
            f.write(response_small.content)
        
        #print("Image saved as tmp/cover.tag.jpg")

        # Download and save cover_big as "tmp/cover.jpg"
        response_big = requests.get(cover_big_url)
        response_big.raise_for_status()
        
        with open(os.path.join("tmp", "cover.jpg"), 'wb') as f:
            f.write(response_big.content)
        
        #print("Image saved as tmp/cover.jpg")
    except Exception as e:
        print(f"Error: {str(e)}")

def get_title_json(title_id):
    api_url = f"https://patron-api-gateway.hoopladigital.com/core/titles/{title_id}"
    try:
        h = headers.copy()
        h['Authorization'] = f'Bearer {authToken}'
        # Fetch the JSON from the API
        response = requests.get(api_url, headers=h)
        response.raise_for_status()  # Raise an exception for any HTTP error

        # Parse the JSON response
        input_json = response.json()
        return input_json
    except requests.exceptions.RequestException as e:
        # Handle any request exceptions (e.g., connection error, timeout)
        print(f"Request Exception: {e}")
        return None
    except ValueError as ve:
        # Handle JSON parsing errors
        print(f"JSON Parsing Error: {ve}")
        return None

def escape_metadata(data):
    # Escapes special characters '=', ';', '#', '\', and newline
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

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from the API: {e}")
    except Exception as ve:
        print(f"Error generating chapters.txt: {ve}")
        raise

def ffmpeg_tag_chapter(book_mediaKey):
    fixed_filename = temp_dir + book_mediaKey + ".notag.m4b"
    chapter_tagged = temp_dir + book_mediaKey + ".m4b"
    
    cmd = [
        "ffmpeg",
        "-i", fixed_filename,
        "-i", chapter_output,
        "-map_metadata", "1", # because chapter_output is a index 1
        "-acodec", "copy",
        chapter_tagged
    ]
    
    try:
        subprocess.run(cmd)
        if os.path.exists(fixed_filename):
            os.remove(fixed_filename)
        if os.path.exists(chapter_output):
            os.remove(chapter_output)
    except Exception as e:
        print(f"Error tagging m4b file with chapter.txt: {str(e)}")
        raise
    
# Tag mutagen needs to happen after chapter is tagged
def tag_mutagen(input_json):
    try:
        # Extract all authors and readers from input_json
        authors = [artist["name"] for artist in input_json["artists"] if artist["relationship"] == "AUTHOR"]
        readers = [artist["name"] for artist in input_json["artists"] if artist["relationship"] == "READER"]
        book_mediaKey = input_json['contents'][0]['mediaKey']
        first_content = input_json['contents'][0]
        title = first_content.get('title', '')
        subtitle = first_content.get('subtitle')

        # Convert displayDate to the desired format
        publishing_date_timestamp = input_json.get("releaseDate", 0) / 1000  # Convert milliseconds to seconds
        publishing_date = datetime.utcfromtimestamp(publishing_date_timestamp).strftime("%Y-%m-%dT%H:%M:%S")

        # Construct the "\xa9alb" value with or without the "-" separator
        if subtitle is not None and subtitle != "":
            album_value = f"{title} - {subtitle}"
        else:
            album_value = title

        metadata_json = {
            "\xa9nam": input_json["title"],
            "\xa9alb": album_value,
            "\xa9ART": ", ".join(authors),
            "\xa9wrt": ", ".join(readers),
            "cprt": f"©{input_json['year']} {input_json['publisher']['name']}",
            "\xa9nrt": ", ".join(readers),
            "\xa9pub": input_json["publisher"]["name"],
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

        cover_image_path = "tmp/cover.tag.jpg"
        audio['covr'] = [mutagen.mp4.MP4Cover(open(cover_image_path, 'rb').read(), imageformat=mutagen.mp4.MP4Cover.FORMAT_JPEG)]

        audio.save()

        # Cleanup smaller cover.tag.jpg used for tagging
        if os.path.exists(cover_image_path):
            os.remove(cover_image_path)

        # create hoopla.metadata.json
        json_file = "tmp/hoopla.metadata.json"

        pretty_json = json.dumps(input_json, indent=4)

        # Write the pretty JSON string to the file
        with open(json_file, 'w') as file:
            file.write(pretty_json)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from the API: {e}")
    except Exception as ve:
        print(f"Error writing metadata file to m4b: {ve}")
        raise


def check_for_ffmpeg():
    try:
        subprocess.Popen(["ffmpeg"],
                         stderr=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL).wait()
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(
            "> Unexpected exception while checking for FFMPEG, please make sure ffmpeg binary is installed and in PATH",
            e)
        return True

def check_for_mp4decrypt():
    try:
        subprocess.Popen(["mp4decrypt"],
                         stderr=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL).wait()
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(
            "Unexpected exception while checking for MP4Decrypt, please make sure mp4decrypt or bento4 is installed and in PATH",
            e)
        return True

def move_and_rename_m4b(input_json):
    # Define the source directory (tmp) and the destination directory (output)
    authors = [artist["name"] for artist in input_json["artists"] if artist["relationship"] == "AUTHOR"]
    book_author = ", ".join(authors)
    book_title = input_json["title"]
    try:
        # Truncate or modify book_title if it's too long for Windows
        #max_title_length = 200  # Adjust as needed
        #if len(book_title) > max_title_length:
        #    book_title = book_title[:max_title_length]

        # Escape any symbols that are not allowed in Windows folder names
        book_title = re.sub(r"([\\/:*?\"<>|])", r"", book_title)
        book_author = re.sub(r"([\\/:*?\"<>|])", r"", book_author)
        abridged = input_json.get("abridged", False)

        # Create the destination directory (output) if it doesn't exist
        if abridged:
            final_dir = os.path.join(output_dir, f"{book_title} - {book_author} [Abridged]")
        else:
            final_dir = os.path.join(output_dir, f"{book_title} - {book_author}")
        os.makedirs(final_dir, exist_ok=True)

        # List all files in the source directory (tmp)
        files_to_move = os.listdir(temp_dir)

        # Initialize a variable to track the renamed .m4b file
        renamed_m4b = None

        # Loop through the files in the source directory
        for file_to_move in files_to_move:
            source_file_path = os.path.join(temp_dir, file_to_move)
            
            # Check if the file is an .m4b file
            if file_to_move.endswith(".m4b"):
                # Rename the .m4b file to book_title.m4b
                renamed_m4b = os.path.join(final_dir, f"{book_title}.m4b")

                # Move and rename the .m4b file
                shutil.move(source_file_path, renamed_m4b)
                mp4 = MP4(renamed_m4b)
                bitrate = mp4.info.bitrate
            else:
                shutil.move(source_file_path, final_dir)

        if renamed_m4b:
            print(f"Downloaded {book_title} - {book_author}")
            print(f"Audiobook processing finished.\nBitrate: {bitrate / 1000} kbps")
        else:
            print("No .m4b file found in the source directory.")
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def check_is_borrowed(book_id):
    json_data = get_hoopla_borrowed_titles(user_id, patron_id, authToken)
    for item in json_data:
        if int(book_id) == int(item['id']):
            return True
    return False

def list_items():
    connect_hoopla()

    json_data = get_hoopla_borrowed_titles(user_id, patron_id, authToken)
    print(f"Audiobooks on loan:\n========================================")
    for item in json_data:
        if item['kind']['id'] == 8: # Audiobook
            book_id = item['contents'][0]['id']
            book_title = item['contents'][0]['title']
            artists = item.get('artists', [])
            book_author = artists[0]['name'] if artists else None  # Need testing of multiple author, ordering etc. 
            print(f"Title: \t\t{book_title}\nAuthor: \t{book_author}\nDownload ID: \t{book_id}\n========================================")

def download_item(book_id):
    connect_hoopla()
    # Implement the logic to download an item with the given ID here
    # Check In Loan
    if check_is_borrowed(book_id):

        # Clear the contents of the "tmp" directory
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Error: {str(e)}")


        content = get_hoopla_item_by_id(book_id)
        circId = content['circId']
        book_mediaKey = content['mediaKey']
        # get x_dt_auth_token
        x_dt_auth_token = get_x_dt_auth_token(book_mediaKey ,circId)
        # get book artid
        # get pssh
        mpd_url = f"https://dash.hoopladigital.com/{book_mediaKey}/Manifest.mpd"
        decrypt_key = widevine(mpd_url, x_dt_auth_token)

        # download m4a
        download_mpd(book_mediaKey, decrypt_key)
        # tag chapter
        book_json = get_title_json(book_id)
        gen_ffmpeg_chapter(book_json)
        ffmpeg_tag_chapter(book_mediaKey)
        tag_mutagen(book_json)
        # move files to folder
        move_and_rename_m4b(book_json)
    else:
        print("Error: The book is not borrowed, or incorrect ID is entered.")
        return

def main():
    # Check FFMPEG and mp4decrypt exist
    has_ffmpeg = check_for_ffmpeg()
    if not has_ffmpeg:
        print("Error: FFMPEG is missing from your system or path! Please install ffmpeg binary")
    has_mp4encrypt = check_for_mp4decrypt()
    if not has_mp4encrypt:
        print("Error: MP4Decrypt is missing from your system of path! Please install bento4 binary")
    
    # Check and create folders
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    if not os.path.exists("config.ini"):
        print("The config.ini file does not exist.\nPlease create a config.ini file according to README file.")

    parser = argparse.ArgumentParser(description="Hoopla Download Tool")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Subparser for the 'list' command
    list_parser = subparsers.add_parser("list", help="List items")

    # Subparser for the 'download' command
    download_parser = subparsers.add_parser("download", help="Download an item")
    download_parser.add_argument("id", type=int, help="ID of the item to download")

    args = parser.parse_args()

    if args.command == "list":
        list_items()
    elif args.command == "download":
        download_item(args.id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
