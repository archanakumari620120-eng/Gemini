import os
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import random
import time
from moviepy.editor import *

# --- API Configuration ---
# Load secrets from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLIENT_SECRET_JSON_STR = os.getenv("CLIENT_SECRET_JSON")
TOKEN_JSON_STR = os.getenv("TOKEN_JSON")

# Set up Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Set up YouTube API
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
    prompt = f"Generate a creative and engaging YouTube video concept. Provide a concise title, a detailed description, and a list of 5-7 relevant tags and 3 hashtags. The topic should be something interesting for a general audience, like 'life hacks', 'fun facts', or 'daily motivation'. Make sure the output is easy to parse. Example output format: Title:..., Description:..., Tags:..., Hashtags:..."
    
    response = model.generate_content(prompt)
    generated_text = response.text

    # Simple parsing to extract the required info
    try:
        title = generated_text.split("Title:")[1].split("Description:")[0].strip()
        description = generated_text.split("Description:")[1].split("Tags:")[0].strip()
        tags_str = generated_text.split("Tags:")[1].split("Hashtags:")[0].strip()
        hashtags_str = generated_text.split("Hashtags:")[1].strip()

        # Convert tags string to a list
        tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
        
        return title, description, tags, hashtags_str

    except IndexError:
        print("Parsing failed, using fallback values.")
        return (
            f"AI Generated Video {int(time.time())}",
            "An interesting video generated automatically by an AI model!",
            ["AI", "Daily Video", "Gemini AI"],
            "#aigenerated #dailyvideos #gemini"
        )

def create_simple_video(title, description):
    """Generates a simple video with text overlay as a placeholder."""
    # In a real-world scenario, you would integrate more advanced AI for visuals and voiceover.
    # This is a basic example using MoviePy.
    
    video_text = f"Title: {title}\n\n{description}"
    
    txt_clip = TextClip(video_text, fontsize=40, color='white', bg_color='black', 
                        size=(1920, 1080), method='caption').set_duration(30)
    
    output_file = "ai_generated_video.mp4"
    txt_clip.write_videofile(output_file, fps=24, codec="libx264")
    
    return output_file

def upload_video_to_youtube(youtube, file_path, title, description, tags):
    """Uploads the video to YouTube."""
    full_description = f"{description}\n\n{' '.join(tags)}" # Add hashtags to description
    
    body = {
        'snippet': {
            'title': title,
            'description': full_description,
            'tags': tags,
            'categoryId': '22'  # Category ID for "People & Blogs"
        },
        'status': {
            'privacyStatus': 'public' # 'public', 'private', or 'unlisted'
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
        
        # Step 2: Generate unique video details
        title, description, tags, hashtags = generate_video_info_with_gemini()
        
        # Step 3: Create the video file
        video_file = create_simple_video(title, description)
        
        # Step 4: Upload the video to YouTube
        # Add hashtags to tags for YouTube upload
        upload_video_to_youtube(youtube, video_file, title, description + " " + hashtags, tags)
        
        print("Video generation and upload process completed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
