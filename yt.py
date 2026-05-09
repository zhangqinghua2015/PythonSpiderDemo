#!/usr/bin/env python3
"""
Extract password (口令) ONLY from YouTube video hard subtitles (画面内嵌文字).
This script completely ignores description, comments, and any other text sources.
It downloads the video, extracts frames in a user-specified time segment (or fallback),
and applies Tesseract OCR (Chinese+English) to find the password.

Environment variables (optional):
  PASSWORD_SEGMENT : "start-end" in seconds, e.g. "120-180" to scan 2:00-3:00.
  OCR_REGION       : normalized coordinates "x,y,w,h" e.g. "0.7,0.8,0.3,0.2".
                     If empty, full frame is scanned.
  FORCE_VIDEO_QUALITY: override yt-dlp format, e.g. "worst[height<=480]".
"""

import os
import re
import sys
import tempfile
import shutil
from pathlib import Path

import yt_dlp
import pytesseract
from PIL import Image
import requests   # unused but kept for compatibility


# ----------------------------------------------------------------------
# Hardcoded configuration (can be overridden by env vars if needed)
CHANNEL_URL = "https://www.youtube.com/@jcnode"
COOKIES_FILE = "cookies.txt"

# Regex patterns (adjust if the password format differs)
PASSWORD_PATTERNS = [
    r'口令[：:]\s*([A-Za-z0-9]{4,8})',
    r'密码[：:]\s*([A-Za-z0-9]{4,8})',
    r'提取码[：:]\s*([A-Za-z0-9]{4,8})',
    r'code[：:]\s*([A-Za-z0-9]{4,8})',
    r'[🔑🔐🔒]\s*([A-Za-z0-9]{4,8})',
    r'([A-Za-z0-9]{4,8})\s*(?:是|为)\s*(?:口令|密码|提取码)',
    r'\b([A-Za-z0-9]{4,8})\b',
]

# ----------------------------------------------------------------------
def _add_cookies(ydl_opts, cookies_file):
    """Add cookiefile to yt-dlp options if the file exists."""
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file
        return True
    return False

def get_latest_video_url(channel_url, cookies_file=None):
    """Fetch the newest video URL from the channel."""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'playlistend': 1,
    }
    _add_cookies(ydl_opts, cookies_file)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        if 'entries' in info and info['entries']:
            first = info['entries'][0]
            video_url = f"https://youtube.com/watch?v={first['id']}"
            return video_url, first.get('title', '')
    return None, None

def extract_from_text(text):
    """Apply all regex patterns to a text and return the first match."""
    if not text:
        return None
    for pat in PASSWORD_PATTERNS:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def ocr_password_from_video(video_url, temp_dir, cookies_file=None):
    """
    Download video (≤480p), extract frames (high density in the target segment),
    run OCR (chi_sim+eng), and return the first password found.
    """
    video_path = Path(temp_dir) / "video.mp4"

    # ---------- Download video in readable quality ----------
    video_format = os.environ.get("FORCE_VIDEO_QUALITY", "worst[height<=480]")
    ydl_opts = {
        'format': video_format,
        'outtmpl': str(video_path),
        'quiet': True,
        'ignore_no_formats_error': True,
        'js_runtimes': {'node': {}},
        'remote_components': 'ejs:github',
    }
    _add_cookies(ydl_opts, cookies_file)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except Exception as e:
        print(f"Video download failed: {e}")
        return None

    if not video_path.exists():
        print("Video file not created.")
        return None

    # ---------- Get video duration ----------
    import subprocess
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
        capture_output=True, text=True
    )
    duration = float(probe.stdout.strip()) if probe.stdout.strip() else 0
    if duration <= 0:
        print("Unable to determine video duration.")
        return None

    # ---------- Parse segmentation ----------
    segment_env = os.environ.get("PASSWORD_SEGMENT", "")
    if segment_env and "-" in segment_env:
        start_sec, end_sec = map(int, segment_env.split("-"))
        start_sec = max(0, start_sec)
        end_sec = min(duration, end_sec)
        segment_mode = True
    else:
        segment_mode = False
        start_sec = end_sec = 0

    # ---------- Frame extraction strategy ----------
    frames_dir = Path(temp_dir) / "frames"
    frames_dir.mkdir(exist_ok=True)

    def extract_frames(segment_start, segment_end, fps, prefix):
        if segment_start >= segment_end:
            return
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-ss', str(segment_start), '-to', str(segment_end),
            '-vf', f'fps={fps}',
            f'{frames_dir}/{prefix}_%04d.png',
            '-y', '-loglevel', 'error'
        ]
        subprocess.run(cmd, check=False)

    if segment_mode:
        # Known segment: high fps (2 frames/sec) over the whole segment
        extract_frames(start_sec, end_sec, 2.0, "focus")
    else:
        # Fallback: high density on first 30s and last 30s, low density on the rest
        extract_frames(0, min(30, duration), 2.0, "start")
        if duration > 60:
            extract_frames(max(0, duration-30), duration, 2.0, "end")
            extract_frames(30, max(30, duration-30), 0.2, "mid")

    # ---------- OCR over all extracted frames ----------
    lang = 'chi_sim+eng'   # Chinese + English
    roi_cfg = os.environ.get("OCR_REGION", "")
    for frame_file in sorted(frames_dir.glob("*.png")):
        img = Image.open(frame_file)
        if roi_cfg:
            # Normalized ROI: x,y,w,h (0-1 each)
            x0, y0, w, h = map(float, roi_cfg.split(','))
            x0 = int(x0 * img.width)
            y0 = int(y0 * img.height)
            w = int(w * img.width)
            h = int(h * img.height)
            roi = img.crop((x0, y0, x0 + w, y0 + h))
        else:
            roi = img   # full frame
        text = pytesseract.image_to_string(roi, lang=lang)
        password = extract_from_text(text)
        if password:
            return password

    return None

def main():
    if not os.path.exists(COOKIES_FILE):
        print("WARNING: cookies.txt not found. YouTube may block the request.")

    temp_dir = tempfile.mkdtemp()
    try:
        video_url, title = get_latest_video_url(CHANNEL_URL, COOKIES_FILE)
        if not video_url:
            print("ERROR: Could not fetch latest video URL")
            sys.exit(1)
        print(f"Processing: {title}\n{video_url}")

        # Direct OCR – no description/comments fallback
        password = ocr_password_from_video(video_url, temp_dir, COOKIES_FILE)
        if password:
            print(f"password={password}")
        else:
            print("password=")
            sys.exit(1)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
