# main.py - Gemini-first uploader (fixed endpoints + payload)
import os, time, json, base64, subprocess, requests, traceback
from pathlib import Path
from moviepy.editor import ImageClip, AudioFileClip
from PIL import Image
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

OUTPUTS = Path("outputs")
OUTPUTS.mkdir(exist_ok=True)
TOKEN_PATH = "token.json"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY and os.path.exists("config.json"):
    try:
        cfg = json.load(open("config.json"))
        GEMINI_API_KEY = cfg.get("GEMINI_API_KEY") or cfg.get("gemini_api_key")
    except Exception:
        pass

if not os.path.exists(TOKEN_PATH):
    raise FileNotFoundError("token.json missing. Add via secret TOKEN_JSON")

creds = Credentials.from_authorized_user_file(TOKEN_PATH)

# Pillow resample fix
try:
    from PIL import Image as PILImage
    RESAMPLE = PILImage.Resampling.LANCZOS if hasattr(PILImage, "Resampling") else PILImage.ANTIALIAS
except Exception:
    RESAMPLE = None

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

# === Gemini Prompt Generation ===
def gen_prompt():
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "Generate a unique, catchy title idea and 1-line creative prompt for a YouTube Short (<=10 words)."}
                    ]
                }
            ]
        }
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        cand = data.get('candidates') or []
        if cand:
            txt = cand[0].get('content', {}).get('parts', [])[0].get('text')
            if txt:
                return txt.strip()
    except Exception as e:
        log("Gemini prompt error: " + str(e))
        log(traceback.format_exc())
    return f"AI Short {int(time.time())}"

# === Gemini Metadata Generation ===
def gen_metadata(prompt):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        req_text = f"Given this prompt: {prompt}\nReturn JSON with keys: title, description, tags, hashtags."
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": req_text}]
                }
            ]
        }
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        cand = data.get('candidates') or []
        if cand:
            txt = cand[0].get('content', {}).get('parts', [])[0].get('text')
            if txt:
                import re
                m = re.search(r'\{.*\}', txt, flags=re.S)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except Exception:
                        pass
                return {"title": txt[:60], "description": txt, "tags": ["AI","shorts"], "hashtags": []}
    except Exception as e:
        log("Gemini metadata error: " + str(e))
        log(traceback.format_exc())
    return {"title": f"AI Short {int(time.time())}", "description": prompt, "tags": ["AI","shorts"], "hashtags": []}

# === Gemini Video ===
def try_gemini_video(prompt):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"Generate a 15-second vertical video (1080x1920) based on: {prompt}"}]
                }
            ]
        }
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        # If direct base64 video data is returned
        cand = data.get("candidates") or []
        for c in cand:
            for p in c.get("content", {}).get("parts", []):
                inline = p.get("inlineData") or {}
                b64 = inline.get("data")
                if b64:
                    out = OUTPUTS / "gemini_video.mp4"
                    out.write_bytes(base64.b64decode(b64))
                    return str(out)
        return None
    except Exception as e:
        log("Gemini video error: " + str(e))
        log(traceback.format_exc())
    return None

# === Gemini Image ===
def try_gemini_image(prompt):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"Generate a vertical 1080x1920 image for: {prompt}"}]
                }
            ]
        }
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        cand = data.get("candidates") or []
        for c in cand:
            for p in c.get("content", {}).get("parts", []):
                inline = p.get("inlineData") or {}
                b64 = inline.get("data")
                if b64:
                    out = OUTPUTS / "gemini_img.jpg"
                    out.write_bytes(base64.b64decode(b64))
                    return str(out)
        return None
    except Exception as e:
        log("Gemini image error: " + str(e))
        log(traceback.format_exc())
    return None

# === Music Downloader ===
def download_music(query="No Copyright background music"):
    out = OUTPUTS / "music.%(ext)s"
    cmd = ["yt-dlp", "--quiet", "-x", "--audio-format", "mp3", "-o", str(out), f"ytsearch1:{query}"]
    try:
        subprocess.run(cmd, check=True)
        for f in OUTPUTS.iterdir():
            if f.suffix.lower() in (".mp3", ".m4a", ".wav"):
                return str(f)
    except Exception as e:
        log("yt-dlp error: " + str(e))
    return None

# === Build Video from Image ===
def build_video_from_image(img_path, music_path, duration=15):
    try:
        img = Image.open(img_path).convert("RGB")
        if RESAMPLE:
            img = img.resize((1080,1920), RESAMPLE)
        else:
            img = img.resize((1080,1920))
        frame = OUTPUTS / "frame.jpg"
        img.save(frame, quality=95)
        clip = ImageClip(str(frame)).set_duration(duration)
        audio = AudioFileClip(music_path).subclip(0, duration)
        clip = clip.set_audio(audio)
        out = OUTPUTS / f"short_{int(time.time())}.mp4"
        clip.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac")
        return str(out)
    except Exception as e:
        log("Build error: " + str(e))
        log(traceback.format_exc())
        return None

# === Upload to YouTube ===
def upload_to_youtube(video_path, metadata):
    try:
        yt = build("youtube","v3", credentials=creds)
        body = {
            "snippet": {
                "title": metadata.get("title"),
                "description": metadata.get("description"),
                "tags": metadata.get("tags") + metadata.get("hashtags", [])
            },
            "status": {"privacyStatus": "public"}
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        log("Uploading...")
        resp = req.execute()
        log("Uploaded id: " + str(resp.get("id")))
        return resp.get("id")
    except Exception as e:
        log("Upload error: " + str(e))
        log(traceback.format_exc())
        return None

# === Job Runner ===
def job():
    log("=== JOB START ===")
    prompt = gen_prompt()
    log("Prompt: " + prompt)
    metadata = gen_metadata(prompt)
    video = try_gemini_video(prompt)
    if video:
        log("Got Gemini video.")
        upload_to_youtube(video, metadata)
        log("=== JOB END ===")
        return
    img = try_gemini_image(prompt)
    if not img:
        log("Gemini image failed. Aborting.")
        return
    music = download_music(prompt + " No Copyright background music")
    if not music:
        log("Music download failed. Aborting.")
        return
    video = build_video_from_image(img, music, duration=15)
    if not video:
        log("Video build failed.")
        return
    upload_to_youtube(video, metadata)
    log("=== JOB END ===")

if __name__ == "__main__":
    job()
                
