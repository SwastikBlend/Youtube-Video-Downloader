import yt_dlp
import os
import subprocess
import threading
import time
import uuid
from flask import Flask, request, render_template, send_file

app = Flask(__name__)

DOWNLOAD_FOLDER = "download"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Path to the cookies file (same directory as the script)
COOKIE_FILE_PATH = os.path.abspath('./youtube.com_cookies.txt')



def merge_video_audio(video_file, audio_file, output_file):
    try:
        print(f"Video File: {video_file}, Audio File: {audio_file}")

        if os.path.getsize(audio_file) < 1024:
            print("Audio file is empty or too small. Skipping merging.")
            return None

        command = [
            'ffmpeg', '-i', video_file, '-i', audio_file,
            '-c:v', 'libx264', '-c:a', 'aac', '-preset', 'ultrafast', output_file
        ]
        subprocess.run(command, check=True)
        print(f"Merged file saved as {output_file}")
        return output_file
    except Exception as e:
        print(f"Error during merging: {str(e)}")
        return None

def download_video_audio(url):
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    common_opts = {
        'noplaylist': True,
        'quiet': False,
        'http_headers': {
            'User-Agent': user_agent
        },
        'cookies': COOKIE_FILE_PATH  
    }

    video_opts = {
        **common_opts,
        'format': 'bestvideo[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(id)s.%(ext)s',
    }

    audio_opts = {
        **common_opts,
        'format': 'bestaudio[ext=mp4]/best',
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(id)s_audio.%(ext)s',
    }

    with yt_dlp.YoutubeDL(video_opts) as ydl_video, yt_dlp.YoutubeDL(audio_opts) as ydl_audio:
        video_info = ydl_video.extract_info(url, download=True)
        audio_info = ydl_audio.extract_info(url, download=True)

    return video_info, audio_info

def async_merge(video_file, audio_file, output_file):
    return merge_video_audio(video_file, audio_file, output_file)

def delayed_cleanup(path, delay=10):
    def cleanup():
        time.sleep(delay)
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")
    threading.Thread(target=cleanup).start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download_video():
    url = request.form.get("url")
    if not url:
        return "NO URL PROVIDED", 400

    try:
        print(f"Received URL: {url}")

        video_info, audio_info = download_video_audio(url)

        video_file = f"{DOWNLOAD_FOLDER}/{video_info['id']}.mp4"
        audio_file = f"{DOWNLOAD_FOLDER}/{audio_info['id']}_audio.mp4"

        max_retries = 10
        retry_delay = 2
        for i in range(max_retries):
            if os.path.exists(video_file) and os.path.exists(audio_file):
                break
            else:
                print(f"Retry {i+1}/{max_retries}: Waiting for files...")
                time.sleep(retry_delay)
        else:
            return "Error: Video or audio file not found.", 400

        output_file = os.path.join(DOWNLOAD_FOLDER, f"{uuid.uuid4()}_merged.mp4")

        
        merge_thread = threading.Thread(target=async_merge, args=(video_file, audio_file, output_file))
        merge_thread.start()
        merge_thread.join()

        delayed_cleanup(DOWNLOAD_FOLDER)

        return send_file(output_file, as_attachment=True, download_name="merged_video.mp4")

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
