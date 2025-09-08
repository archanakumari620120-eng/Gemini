import os, time, json, base64, requests, subprocess, traceback
from pathlib import Path
from moviepy.editor import ImageClip, AudioFileClip
from PIL import Image
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# === Paths ===
OUTPUTS = Path("outputs")
OUTPUTS.mkdir(exist_ok=True)

# === API Keys from secrets ===
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")

# === YouTube Auth ===
creds = Credentials.from_authorized_user_file("token.json")

# === Pillow Resample Fix ===
try:
    RESAMPLE = Image.Resampling.LANCZOS
except:
    RESAMPLE = Image.ANTIALIAS

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

# === Gemini Prompt ===
def gen_prompt():
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
        payload = {
            "contents": [{"parts": [{"text": "Generate a unique short video idea for YouTube Shorts"}]}]
        }
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=20)
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return txt.strip()
    except Exception as e:
        log(f"Gemini prompt error: {e}")
        return f"AI Short {int(time.time())}"

# === Gemini Metadata ===
def gen_metadata(prompt):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
        req_text = f"""
        Given this prompt: {prompt}
        Return JSON only: {{"title":"Short title <=60 chars","description":"1 line desc","tags":["AI","shorts"],"hashtags":["#AI","#shorts"]}}
        """
        payload = {"contents": [{"parts": [{"text": req_text}]}]}
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=20)
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]

        import re
        m = re.search(r'\{.*\}', txt, flags=re.S)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        log(f"Gemini metadata error: {e}")
    return {"title": f"AI Short {int(time.time())}", "description": prompt, "tags": ["AI","shorts"], "hashtags": ["#AI"]}

# === Gemini Video ===
def try_gemini_video(prompt):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-video-latest:generateVideo"
        payload = {"prompt": prompt, "config": {"duration_seconds": 15, "resolution": "1080x1920"}}
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        if "video" in data:
            out = OUTPUTS / "gemini_video.mp4"
            out.write_bytes(base64.b64decode(data["video"]))
            return str(out)
    except Exception as e:
        log(f"Gemini video error: {e}")
    return None

# === Hugging Face Video ===
def try_hf_video(prompt):
    try:
        url = "https://api-inference.huggingface.co/models/damo-vilab/text-to-video-ms-1.7b"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        r = requests.post(url, headers=headers, json={"inputs": prompt}, timeout=120)
        if r.ok:
            out = OUTPUTS / "hf_video.mp4"
            out.write_bytes(r.content)
            return str(out)
    except Exception as e:
        log(f"HuggingFace video error: {e}")
    return None

# === Hugging Face Image ===
def try_hf_image(prompt):
    try:
        url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        r = requests.post(url, headers=headers, json={"inputs": prompt}, timeout=60)
        if r.ok:
            out = OUTPUTS / "hf_image.jpg"
            out.write_bytes(r.content)
            return str(out)
    except Exception as e:
        log(f"HuggingFace image error: {e}")
    return None

# === Music Downloader ===
def download_music():
    out = OUTPUTS / "music.%(ext)s"
    cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", str(out), "ytsearch1:No Copyright background music"]
    try:
        subprocess.run(cmd, check=True)
        for f in OUTPUTS.iterdir():
            if f.suffix in [".mp3", ".m4a", ".wav"]:
                return str(f)
    except Exception as e:
        log(f"Music error: {e}")
    return None

# === Build Video from Image ===
def build_video_from_image(img_path, music_path, duration=15):
    try:
        img = Image.open(img_path).convert("RGB").resize((1080,1920), RESAMPLE)
        frame = OUTPUTS / "frame.jpg"
        img.save(frame, quality=95)
        clip = ImageClip(str(frame)).set_duration(duration)
        audio = AudioFileClip(music_path).subclip(0, duration)
        clip = clip.set_audio(audio)
        out = OUTPUTS / f"short_{int(time.time())}.mp4"
        clip.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac")
        return str(out)
    except Exception as e:
        log(f"Video build error: {e}")
    return None

# === Upload to YouTube ===
def upload_to_youtube(video_path, metadata):
    try:
        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"] + metadata["hashtags"]
            },
            "status": {"privacyStatus": "public"}
        }
        req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(video_path))
        resp = req.execute()
        log(f"✅ Uploaded Video ID: {resp.get('id')}")
    except Exception as e:
        log(f"Upload error: {e}")

# === Job Runner ===
def job():
    log("=== JOB START ===")
    prompt = gen_prompt()
    metadata = gen_metadata(prompt)

    video = try_gemini_video(prompt)
    if not video:
        video = try_hf_video(prompt)
    if not video:
        img = try_hf_image(prompt)
        if img:
            music = download_music()
            if music:
                video = build_video_from_image(img, music)

    if video:
        upload_to_youtube(video, metadata)
    else:
        log("❌ Video generation failed.")
    log("=== JOB END ===")

if __name__ == "__main__":
    job()
        
