import os, json, base64, time, requests
from openai import OpenAI
from moviepy.editor import ImageClip, AudioFileClip
import pyttsx3
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import schedule

# --- Config ---
config = json.load(open("config.json"))
topic = config["topic"]
video_count = config["video_count"]
video_duration = config["video_duration"]
auto_upload = config.get("auto_upload", True)

# --- Secrets / Env ---
gemini_api_key = os.environ.get("GEMINI_API_KEY")
huggingface_token = os.environ.get("HUGGINGFACE_TOKEN")
client_secret_file = "client_secret.json"
token_file = "token.json"

client = OpenAI(api_key=gemini_api_key)
os.makedirs("assets/images", exist_ok=True)
os.makedirs("assets/voices", exist_ok=True)
os.makedirs("assets/videos", exist_ok=True)

# --- HuggingFace Image ---
def generate_image_hf(prompt, file_path):
    api_url = "https://api-inference.huggingface.co/models/stable-diffusion-v1-5"
    headers = {"Authorization": f"Bearer {huggingface_token}"}
    payload = {"inputs": prompt}
    resp = requests.post(api_url, headers=headers, json=payload)
    if resp.status_code == 200:
        with open(file_path, "wb") as f:
            f.write(resp.content)
        print(f"HuggingFace image generated: {file_path}")
    else:
        print("HF image generation failed:", resp.text)

# --- Automation Task ---
def run_automation():
    print("Starting Automation Cycle...")

    # 1️⃣ Scripts
    scripts = []
    for _ in range(video_count):
        resp = client.chat.completions.create(
            model="gemini-1.5",
            messages=[{"role": "user", "content": f"Write a {video_duration}-second engaging YouTube Short script on '{topic}'."}]
        )
        scripts.append(resp.choices[0].message.content)

    # 2️⃣ Images
    for i, script in enumerate(scripts):
        image_file = f"assets/images/image_{i}.png"
        try:
            response = client.images.generate(
                model="models/image-generator-1",
                prompt=f"{topic}, cinematic, high detail, 1080x1920",
                size="1080x1920"
            )
            image_bytes = base64.b64decode(response.data[0].b64_json)
            with open(image_file, "wb") as f:
                f.write(image_bytes)
            print(f"Gemini image generated: {image_file}")
        except Exception as e:
            print("Gemini failed, using HuggingFace:", e)
            generate_image_hf(f"{topic}, cinematic, high detail, 1080x1920", image_file)

    # 3️⃣ Voice + Video
    engine = pyttsx3.init()
    for i, script in enumerate(scripts):
        voice_file = f"assets/voices/voice_{i}.mp3"
        engine.save_to_file(script, voice_file)
        engine.runAndWait()

        video_file = f"assets/videos/video_{i}.mp4"
        clip = ImageClip(f"assets/images/image_{i}.png", duration=video_duration)
        audio = AudioFileClip(voice_file)
        final = clip.set_audio(audio)
        final.write_videofile(video_file, fps=24)
        print(f"Video created: {video_file}")

    # 4️⃣ YouTube Upload
    if auto_upload:
        creds = Credentials.from_authorized_user_file(token_file, ["https://www.googleapis.com/auth/youtube.upload"])
        youtube = build("youtube", "v3", credentials=creds)

        def upload_video(file_path, title):
            request = youtube.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {"title": title, "description": f"Check out {topic}!", "tags": ["AI","Tech","Shorts"]},
                    "status": {"privacyStatus": "public"}
                },
                media_body=file_path
            )
            response = request.execute()
            print(f"Uploaded: {title}")

        for i, vf in enumerate(sorted(os.listdir("assets/videos"))):
            upload_video(f"assets/videos/{vf}", f"{topic} Short {i}")

    # 5️⃣ Clean up
    for folder in ["images","voices","videos"]:
        folder_path = f"assets/{folder}"
        for f in os.listdir(folder_path):
            os.remove(os.path.join(folder_path, f))
    print("Automation cycle completed!")

# --- Scheduler for Local PC ---
schedule.every(config.get("upload_interval_minutes", 60)).minutes.do(run_automation)

print("Scheduler started. Press Ctrl+C to stop.")
while True:
    schedule.run_pending()
    time.sleep(10)
        
