# main.py — Final working version with Gemini + HF + fallback
import os, time, json, random, traceback, requests
from pathlib import Path
from PIL import Image
from moviepy.editor import ImageClip, AudioFileClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

try:
    import google.genai as genai
    HAVE_GEMINI_LIB = True
except Exception:
    HAVE_GEMINI_LIB = False

with open("config.json","r") as f:
    CONFIG=json.load(f)

OUTPUTS=Path("outputs");OUTPUTS.mkdir(exist_ok=True)
IMAGES_DIR=Path("images");MUSIC_DIR=Path("music")
TOKEN_FILE="token.json"

if hasattr(Image,"Resampling"):
    RESAMPLE=Image.Resampling.LANCZOS
else:
    RESAMPLE=Image.ANTIALIAS

creds=Credentials.from_authorized_user_file(TOKEN_FILE)

def log(s): print(f"[{time.strftime('%H:%M:%S')}] {s}",flush=True)

def safe_write(path,b):
    with open(path,"wb") as f:f.write(b)

def get_prompt():
    try:
        if HAVE_GEMINI_LIB:
            genai.configure(api_key=CONFIG.get("GEMINI_API_KEY"))
            client=genai.Client()
            r=client.generate_text(model="gemini-2.5",prompt="Give a short idea for a YouTube Short (<=12 words).")
            t=getattr(r,"text",None)
            if t:return t.strip()
        else:
            k=CONFIG.get("GEMINI_API_KEY")
            if k:
                u="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5:generateContent"
                p={"contents":[{"parts":[{"text":"Give a short idea for a YouTube Short (<=12 words)."}]}]}
                r=requests.post(u,params={"key":k},json=p,timeout=20)
                d=r.json();c=d.get("candidates") or []
                if c:txt=c[0]["content"]["parts"][0]["text"];return txt.strip()
    except Exception as e: log("Prompt fail "+str(e))
    return random.choice(["Quick hack tip","Amazing space fact","Motivational quote","Funny joke"])

def gen_hf_image(prompt):
    try:
        token=CONFIG.get("HF_API_KEY")
        if not token:return None
        url="https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2"
        h={"Authorization":f"Bearer {token}"}
        r=requests.post(url,headers=h,json={"inputs":prompt},timeout=60)
        if r.status_code==200:
            out=OUTPUTS/"hf_img.jpg";safe_write(out,r.content);return str(out)
    except Exception as e: log("HF fail "+str(e))
    return None

def pick_manual_image():
    imgs=[p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in(".jpg",".png",".jpeg")] if IMAGES_DIR.exists() else []
    return str(random.choice(imgs)) if imgs else None

def pick_music():
    mus=[p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in(".mp3",".wav")] if MUSIC_DIR.exists() else []
    return str(random.choice(mus)) if mus else None

def build_video(img,music,duration=15):
    img2=Image.open(img).convert("RGB").resize((1080,1920),RESAMPLE)
    fixed=OUTPUTS/"frame.jpg";img2.save(fixed)
    clip=ImageClip(str(fixed)).set_duration(duration)
    audio=AudioFileClip(music).subclip(0,duration)
    clip=clip.set_audio(audio)
    out=OUTPUTS/f"short_{int(time.time())}.mp4"
    clip.write_videofile(str(out),fps=30,codec="libx264",audio_codec="aac")
    return str(out)

def upload(video,prompt):
    yt=build("youtube","v3",credentials=creds)
    body={"snippet":{"title":prompt[:55],"description":prompt+"\nAuto","tags":["AI","Shorts"]},"status":{"privacyStatus":"public"}}
    req=yt.videos().insert(part="snippet,status",body=body,media_body=MediaFileUpload(video))
    r=req.execute();log("Uploaded video id "+r.get("id","?"))

def job():
    log("=== JOB START ===")
    prompt=get_prompt();log("Prompt: "+prompt)
    img=gen_hf_image(prompt) or pick_manual_image()
    music=pick_music()
    if not img or not music:log("No assets");return
    video=build_video(img,music,int(CONFIG.get("video_generation",{}).get("duration_seconds",15)))
    if video: upload(video,prompt)
    log("=== JOB END ===")

if __name__=="__main__": job()
