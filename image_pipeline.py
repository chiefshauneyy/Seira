import os
import requests
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class ImagePipeline:
    def __init__(self):
        self.nasa_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        self.base_path = "./assets/daily_posts"
        # Ensure the directory exists
        os.makedirs(self.base_path, exist_ok=True)

    def generate_free_image(self, prompt):
        """Generates an image for free via Pollinations.ai."""
        print(f"🎨 Seira is synthesizing visual data: {prompt[:50]}...")
        
        # Encode the prompt for a URL
        encoded_prompt = urllib.parse.quote(prompt)
        # We can specify model (flux, turbo, etc.) and dimensions
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux"
        
        return self._save_image(image_url, "seira_gen")

    def fetch_nasa_apod(self):
        """Fetches today's Astronomy Picture of the Day (Free)."""
        print("🔭 Seira is scanning the stars (NASA APOD)...")
        url = f"https://api.nasa.gov/planetary/apod?api_key={self.nasa_key}"
        try:
            res = requests.get(url).json()
            if res.get("media_type") == "image":
                return self._save_image(res["url"], "nasa_astro"), res.get("explanation")
        except Exception as e:
            print(f"❌ NASA fetch failed: {e}")
        return None, "Intel fetch failed."

    def _save_image(self, url, prefix):
        """Downloads and saves the image."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.jpg"
        filepath = os.path.join(self.base_path, filename)
        
        response = requests.get(url)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"✅ Asset secured: {filepath}")
            return filepath
        else:
            print(f"❌ Failed to download image. Status: {response.status_code}")
            return None

if __name__ == "__main__":
    pipeline = ImagePipeline()
    # Test the free generation
    path = pipeline.generate_free_image("Cybernetic goddess Seira, tactical visor, cinematic lighting, 8k")
    print(f"Image saved at: {path}")