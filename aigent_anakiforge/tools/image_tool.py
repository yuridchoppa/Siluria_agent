import os
import requests
from openai import OpenAI
from config import OPENAI_API_KEY, IMAGE_GEN_MODEL, WORKSPACE_DIR

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_image(prompt: str, filename: str) -> str:
    """
    Generate an image using DALL-E 3 based on a text prompt and save it to the workspace.
    """
    try:
        response = client.images.generate(
            model=IMAGE_GEN_MODEL,
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url

        # Download and save the image
        img_data = requests.get(image_url).content

        filepath = os.path.join(WORKSPACE_DIR, filename)
        with open(filepath, 'wb') as handler:
            handler.write(img_data)

        return f"Image successfully generated and saved to {filepath}"
    except Exception as e:
        return f"Error generating image: {str(e)}"
