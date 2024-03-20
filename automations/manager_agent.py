from openai import OpenAI, RateLimitError
from base64 import b64encode
from dotenv import load_dotenv
import time
import os
from utils.json_utils import extract_json
import aiofiles
from web_agent import JoshyTrain

load_dotenv()

port = os.getenv("PORT")

model = OpenAI()
model.timeout = 30


class Manager:
    def __init__(self, page) -> None:
        self.base64_image = None
        self.instructions = """
            TBD
        """
        self.messages = [
            {"role": "system", "content": self.instructions},
        ]
        self.page = page
        self.web_agent = JoshyTrain(page)

    def image_b64(self, image):
        with open(image, "rb") as f:
            return b64encode(f.read()).decode("utf-8")

    async def write_text_to_file(self, file_name, text):
        async with aiofiles.open(file_name, "w") as file:
            await file.write(text)

    async def write_image_to_file(self, file_name, image):
        async with aiofiles.open(file_name, "wb") as file:
            await file.write(image)

    async def process_page(self):
        try:
            await self.page.wait_for_timeout(2000)
            print("Taking screenshot...")
            screenshot = await self.page.screenshot(
                path="screenshot.png", full_page=True
            )
            await self.write_image_to_file("screenshot.jpg", screenshot)
        except Exception as e:
            print(e)
        self.base64_image = self.image_b64("screenshot.jpg")

    async def chat(self, input):
        await self.process_page()
        self.messages.append(
            {"role": "user", "content": input},
        )

        print("User:", input)

        while True:
            screenshot_msg = ""
            if self.base64_image:
                screenshot_msg = {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{self.base64_image}"
                            },
                        },
                        {
                            "type": "text",
                            "text": f"""Here's the screenshot of the website you are on right now.""",
                        },
                    ],
                }

                self.base64_image = None

            for attempt in range(3):
                try:
                    response = model.chat.completions.create(
                        model="gpt-4-vision-preview",
                        messages=(
                            [*self.messages, screenshot_msg]
                            if screenshot_msg
                            else self.messages
                        ),
                        max_tokens=1024,
                    )
                    break
                except RateLimitError as e:
                    print(
                        f"Rate limit exceeded, attempt {attempt + 1} of {3}. Retrying in {120} seconds..."
                    )
                    time.sleep(120)

            if not response:
                raise Exception("API call failed after retrying")

            message = response.choices[0].message
            message_text = message.content

            print("Manager Assistant:", message_text)

            data = extract_json(message_text)

            if data and data["message_to_web_agent"]:
                await self.web_agent.chat(data["message_to_web_agent"])
                

            self.messages.append(
                {
                    "role": "assistant",
                    "content": message_text,
                }
            )
            return message_text
