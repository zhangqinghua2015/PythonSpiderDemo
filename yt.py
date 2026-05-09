#!/usr/bin/env python3
"""
Extract password (口令) from the first video of a given YouTube channel.
Workflow:
1. Fetch channel's video list, pick the newest video.
2. Extract password from video description.
3. If not found, fetch comments (requires cookies.txt) and check pinned/normal comments.
4. If still not found, download low-quality video, extract frames, run OCR.
5. Output extracted password (or empty if none found).
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
import requests


# ----------------------------------------------------------------------
# Configuration
CHANNEL_URL = "https://www.youtube.com/@jcnode"
# Regex patterns for common password formats (4-8 alphanumeric, case-insensitive)
PASSWORD_PATTERNS = [
    r'口令[：:]\s*([A-Za-z0-9]{4,8})',
    r'密码[：:]\s*([A-Za-z0-9]{4,8})',
    r'提取码[：:]\s*([A-Za-z0-9]{4,8})',
    r'code[：:]\s*([A-Za-z0-9]{4,8})',
    r'[🔑🔐🔒]\s*([A-Za-z0-9]{4,8})',
    r'([A-Za-z0-9]{4,8})\s*(?:是|为)\s*(?:口令|密码|提取码)',
    r'\b([A-Za-z0-9]{4,8})\b',   # fallback: standalone 4-8 alnum (may produce false positives)
]

# ----------------------------------------------------------------------
def get_latest_video_url(channel_url):
    """Fetch the newest video URL from a YouTube channel."""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'playlistend': 1,       # only first video
        'force_generic_extractor': False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        if 'entries' in info and info['entries']:
            first_entry = info['entries'][0]
            video_url = f"https://youtube.com/watch?v={first_entry['id']}"
            return video_url, first_entry.get('title', '')
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


def get_video_description(video_url):
    """Return the description of the video."""
    ydl_opts = {'quiet': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info.get('description', '')


def get_pinned_comment(video_url, cookies_file=None):
    """Attempt to fetch pinned comment using yt-dlp with optional cookies."""
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'writecomments': True,
        'commentlimit': 10,
        'max_comments': 10,
        'extract_flat': False,
    }
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            comments = info.get('comments', [])
            # find pinned comment
            for c in comments:
                if c.get('pinned') is True:
                    return c.get('text', '')
            # if no pinned, return first comment
            if comments:
                return comments[0].get('text', '')
    except Exception as e:
        print(f"Comment extraction failed (maybe need cookies): {e}")
    return None


def ocr_password_from_video(video_url, temp_dir):
    """
    Download low-quality video, extract frames, run OCR.
    Returns first match found, or None.
    """
    # 1. Download worst quality video
    video_path = Path(temp_dir) / "video.mp4"
    ydl_opts = {
        'format': 'worst[ext=mp4]',
        'outtmpl': str(video_path),
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    if not video_path.exists():
        return None

    # 2. Extract frames (1 frame every 2 seconds, only first 5 minutes)
    import subprocess
    frames_dir = Path(temp_dir) / "frames"
    frames_dir.mkdir(exist_ok=True)

    # Get video duration
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
         'default=noprint_wrappers=1:nokey=1', str(video_path)],
        capture_output=True, text=True
    )
    duration = float(probe.stdout.strip())

    # Only first 5 minutes (most likely place for password)
    limit_sec = min(300, duration) if duration else 300

    cmd = [
        'ffmpeg', '-i', str(video_path), '-t', str(limit_sec),
        '-vf', 'fps=0.5', f'{frames_dir}/frame_%04d.png',
        '-y', '-loglevel', 'error'
    ]
    subprocess.run(cmd, check=False)

    # 3. OCR each frame
    for frame_file in sorted(frames_dir.glob("*.png")):
        # optional: crop to bottom-right quarter (where passwords often appear)
        img = Image.open(frame_file)
        w, h = img.size
        # crop bottom-right region (1/4th)
        roi = img.crop((w * 3 // 4, h * 3 // 4, w, h))
        text = pytesseract.image_to_string(roi, lang='eng')
        password = extract_from_text(text)
        if password:
            return password

    return None


def main():
    cookies_file = "cookies.txt"   # expected to be present when secret provided
    temp_dir = tempfile.mkdtemp()
    try:
        # Step 1: Get latest video URL
        video_url, title = get_latest_video_url(CHANNEL_URL)
        if not video_url:
            print("ERROR: Could not extract video URL from channel")
            sys.exit(1)
        print(f"Latest video: {title} - {video_url}")

        # Step 2: Extract from description
        desc = get_video_description(video_url)
        password = extract_from_text(desc)
        if password:
            print(f"password={password}")
            return

        # Step 3: Extract from comments (if cookies available)
        if os.path.exists(cookies_file):
            comment_text = get_pinned_comment(video_url, cookies_file)
            if comment_text:
                password = extract_from_text(comment_text)
                if password:
                    print(f"password={password}")
                    return

        # Step 4: OCR from video frames
        print("Attempting OCR on video frames...")
        password = ocr_password_from_video(video_url, temp_dir)
        if password:
            print(f"password={password}")
            return

        # Not found
        print("password=")
        sys.exit(1)

    finally:
        # Clean up temp files
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
