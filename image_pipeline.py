import os
import requests
import urllib.parse
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class ImagePipeline:
    def __init__(self):
        self.nasa_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        
        # Use absolute pathing to ensure the purge system finds the right folder
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_path = os.path.join(self.base_dir, "assets")
        
        # Ensure the directory exists
        os.makedirs(self.base_path, exist_ok=True)

    def generate_free_image(self, prompt):
        """Generates an image for free via Pollinations.ai with randomized seeds."""
        print(f"🎨 Seira is synthesizing visual data: {prompt[:50]}...")
        
        # Add a random seed to ensure visual variety for daily posts
        seed = random.randint(0, 999999)
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Flux model with cinematic 16:9 or 1:1 aspect ratio
        # Added seed and specific dimensions for high-quality results
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed={seed}"
        
        return self._save_image(image_url, "seira_gen")

    def fetch_nasa_apod(self):
        """Fetches today's Astronomy Picture of the Day."""
        print("🔭 Seira is scanning the stars (NASA APOD)...")
        url = f"https://api.nasa.gov/planetary/apod?api_key={self.nasa_key}"
        try:
            res = requests.get(url, timeout=15).json()
            if res.get("media_type") == "image":
                return self._save_image(res["url"], "nasa_astro"), res.get("explanation")
        except Exception as e:
            print(f"❌ NASA fetch failed: {e}")
        return None, "Intel fetch failed."

    def _save_image(self, url, prefix):
        """Downloads and saves the image with timeout protection."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.jpg"
        filepath = os.path.join(self.base_path, filename)
        
        try:
            # Added 30-second timeout to prevent the bot from hanging
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Asset secured: {filepath}")
                return filepath
            else:
                print(f"❌ Failed to download image. Status: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Critical download error: {e}")
            return None

if __name__ == "__main__":
    pipeline = ImagePipeline()
    # Test the free generation
    path = pipeline.generate_free_image("Cinematic Dune aesthetic, brutalist monolith, vast scale, 8k")
    print(f"Image saved at: {path}")