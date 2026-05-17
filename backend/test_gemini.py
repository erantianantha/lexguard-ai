import asyncio
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    try:
        res = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents="test",
            config=types.GenerateContentConfig(system_instruction="reply test")
        )
        print("Success:", res.text)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
