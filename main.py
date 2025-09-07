                        size=(1920, 1080), method='caption').set_duration(30)
    
    output_file = "ai_generated_video.mp4"
    txt_clip.write_videofile(output_file, fps=24, codec="libx264")
    
    return output_file

import os
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import random
import time
import requests
from moviepy.editor import *

# --- Configuration from GitHub Secrets ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TOKEN_JSON_STR = os.getenv("TOKEN_JSON")

# Gemini AI Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# YouTube API Setup
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service():
    """Authenticates with YouTube using the token from GitHub Secrets."""
    creds_info = json.loads(TOKEN_JSON_STR)
    credentials = Credentials.from_authorized_user_info(info=creds_info, scopes=SCOPES)
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)

def generate_video_info_with_gemini():
    """Generates unique video details (title, description, tags) using Gemini AI."""
    prompt = "Generate a creative and engaging YouTube video concept. The video should be a fun fact, a simple life hack, or a motivational thought for a general audience. Provide a concise title, a detailed description, and a list of 5-7 relevant tags and 3 hashtags. The output format should be: Title:..., Description:..., Tags:..., Hashtags:..."
    
    response = model.generate_content(prompt)
    generated_text = response.text
    print(f"Gemini AI Response:\n{generated_text}\n")

    # Simple parsing to extract the required info
    try:
        title = generated_text.split("Title:")[1].split("Description:")[0].strip()
        description = generated_text.split("Description:")[1].split("Tags:")[0].strip()
        tags_str = generated_text.split("Tags:")[1].split("Hashtags:")[0].strip()
        hashtags_str = generated_text.split("Hashtags:")[1].strip()

        tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
        
        return title, description, tags, hashtags_str

    except IndexError:
        print("Parsing failed, using fallback values.")
        unique_id = int(time.time())
        return (
            f"AI Generated Video {unique_id}",
            "An interesting video generated automatically by an AI model!",
            ["AI", "Daily Video", "Gemini AI"],
            "#aigenerated #dailyvideos #gemini"
        )

def create_video_from_script(title, description):
    """
    Generates a video from a given script. 
    This is a placeholder function. In a real-world scenario, you would
    integrate a video generation API like Veo, Sora, or Pika.
    """
    print("Creating video from script...")
    
    # Create a simple video with text and a random background color
    bg_color = random.choice(['#1e1e1e', '#2c3e50', '#8e44ad', '#3498db', '#2ecc71'])
    video_text = f"{title}\n\n{description}"
    
    txt_clip = TextClip(video_text, fontsize=50, color='white', bg_color=bg_color,
                        size=(1920, 1080), method='caption').set_duration(30)
    
    output_file = f"ai_generated_video_{int(time.time())}.mp4"
    txt_clip.write_videofile(output_file, fps=24, codec="libx264")
    
    print(f"Video saved as {output_file}")
    return output_file

def upload_video_to_youtube(youtube, file_path, title, description, tags, hashtags):
    """Uploads the video to YouTube."""
    full_description = f"{description}\n\n{' '.join(hashtags.split())}"
    
    body = {
        'snippet': {
            'title': title,
            'description': full_description,
            'tags': tags,
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public'
        }
    }

    insert_request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=file_path
    )
    
    print(f"Uploading video with title: {title}")
    response = insert_request.execute()
    print(f"Video uploaded successfully! Video ID: {response.get('id')}")
    return response

if __name__ == "__main__":
    try:
        # Step 1: Get YouTube authenticated service
        youtube = get_authenticated_service()
        
        # Step 2: Generate unique video details using Gemini
        title, description, tags, hashtags = generate_video_info_with_gemini()
        
        # Step 3: Create the video file
        video_file = create_video_from_script(title, description)
        
        # Step 4: Upload the video to YouTube
        upload_video_to_youtube(youtube, video_file, title, description, tags, hashtags)
        
        print("Video generation and upload process completed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
    
