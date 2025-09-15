import os, time, json, base64, requests, traceback
from pathlib import Path
from moviepy.editor import ImageClip
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

OUTPUTS = Path("outputs")
OUTPUTS.mkdir(exist_ok=True)

# Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TOKEN_JSON = "token.json"  # tumhare repo me rakha hoga

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

# === 1. Gemini Image Generate ===
def generate_image(prompt):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }
        body = {
            "contents": [{"parts": [{"text": f"Generate an image of: {prompt}"}]}],
            "generationConfig": {"responseMimeType": "image/png"}
        }
        r = requests.post(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        img_b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        img_bytes = base64.b64decode(img_b64)
        path = OUTPUTS / f"img_{int(time.time())}.png"
        path.write_bytes(img_bytes)
        return str(path)
    except Exception as e:
        log(f"Image gen error: {e}\n{traceback.format_exc()}")
        return None

# === 2. Image → Video ===
def build_video_from_image(img_path, duration=10):
    try:
        clip = ImageClip(img_path).set_duration(duration)
        out = OUTPUTS / f"video_{int(time.time())}.mp4"
        clip.write_videofile(str(out), fps=24, codec="libx264")
        return str(out)
    except Exception as e:
        log(f"Video build error: {e}")
        return None

# === 3. Upload to YouTube ===
def upload_to_youtube(video_path, title="AI Short", tags=["AI","shorts"]):
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_JSON, scopes=["https://www.googleapis.com/auth/youtube.upload"])
        if not creds.valid:
            creds.refresh(GoogleRequest())
            with open(TOKEN_JSON, "w") as f:
                f.write(creds.to_json())
        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title,
                "description": title,
                "tags": tags
            },
            "status": {"privacyStatus": "public"}
        }
        media = MediaFileUpload(video_path, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while True:
            status, resp = req.next_chunk()
            if resp:
                break
        log(f"✅ Uploaded video id: {resp.get('id')}")
        return True
    except Exception as e:
        log(f"Upload error: {e}\n{traceback.format_exc()}")
        return False

def main():
    log("=== Job Start ===")
    prompt = "A futuristic city skyline at night with neon lights"
    img = generate_image(prompt)
    if not img:
        log("Image failed")
        return
    video = build_video_from_image(img)
    if not video:
        log("Video failed")
        return
    upload_to_youtube(video, title="AI Futuristic City #shorts")
    log("=== Job End ===")

if __name__ == "__main__":
    main()
        
