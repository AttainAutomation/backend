from openai import OpenAI
import openai
from base64 import b64encode
import json
from dotenv import load_dotenv
from tarsier import Tarsier, GoogleVisionOCRService
import time
import re
import os
import requests
import aiofiles

load_dotenv()

port = os.getenv("PORT")
google_cloud_credentials = json.loads(os.getenv("GOOGLE_CLOUD_CREDENTIALS"))

ocr_service = GoogleVisionOCRService(google_cloud_credentials)
tarsier = Tarsier(ocr_service)

model = OpenAI()
model.timeout = 30


class JoshyTrain:
    def __init__(self, page) -> None:
        self.base64_image = None
        self.tag_to_xpath = {}
        self.page_text = ""
        self.instructions = """
            You are a website browsing agent. You will be given instructions on what to do by browsing. You are connected to a web browser and you will be given the screenshot and the text representation of the website you are on. 
            You can interact with the website by clicking on links, filling in text boxes, and going to a specific URL.
            
            [#ID]: text-insertable fields (e.g. textarea, input with textual type)
            [@ID]: hyperlinks (<a> tags)
            [$ID]: other interactable elements (e.g. button, select)
            [ID]: plain text (if you pass tag_text_elements=True)

            You can go to a specific URL by answering with the following JSON format:
            {"url": "url goes here"}

            You can click links on the website by referencing the ID before the component in the text representation, by answering in the following JSON format:
            {"click": "ID"}

            You can fill in text boxes by referencing the ID before the component in the text representation, by answering in the following JSON format:
            {"input": {"select": "ID", "text": "Text to type"}}

            Don't include the #, @, or $ in the ID when you are answering with the JSON format.

            The IDs are always integer values.

            You can press any key on the keyboard by answering with the following JSON format:
            {"keyboard": "key"}
            make sure your input for "key" works for the page.keyboard.press method from python playwright.

            You can go back, go forward, or reload the page by answering with the following JSON format:
            {"navigation": "back"}
            {"navigation": "forward"}
            {"navigation": "reload"}

            You can record the reachout by answering with the following JSON format:
            {"record reachout": {"email": "Email", "keyword": "Keyword", "question": "Question", "name": "Name of the reachout"}}

            You can delete the reachout by answering with the following JSON format:
            {"delete reachout": {"account": "Account", "email": "Email", "keyword": "Keyword", "question": "Question", "name": "Name of the reachout"}}

            You can record the response by answering with the following JSON format:
            {"record response": {"account": "Account", "email": "Email", "keyword": "Keyword", "question": "Question", "name": "Name of the reachout", "response": "Response"}}



            When responding with the JSON format, only include ONE JSON object and nothing else, no need for explanation.

            Once you are on a URL and you have found the answer to the user's question, you can answer with a regular message.

            Use google search by set a sub-page like 'https://google.com/search?q=search
        """
        self.messages = [
            {"role": "system", "content": self.instructions},
        ]
        self.page = page
        self.step_count = 1

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
            screenshot, tag_to_xpath = await tarsier.page_to_image(self.page)
            await self.write_image_to_file("screenshot.jpg", screenshot)

            print("Getting text...")
            page_text = tarsier._run_ocr(screenshot)
            await self.write_text_to_file("page_text.txt", page_text)
        except Exception as e:
            print(e)

        self.base64_image = self.image_b64("screenshot.jpg")
        self.tag_to_xpath = tag_to_xpath
        self.page_text = page_text

    def extract_json(self, message):
        # Normalize newlines and remove control characters except for tab
        normalized_message = re.sub(r'[\r\n]+', ' ', message)  # Replace newlines with spaces
        sanitized_message = re.sub(r'[^\x20-\x7E\t]', '', normalized_message)  # Remove non-printable chars

        # Attempt to find JSON starting and ending points without nested checks
        start = sanitized_message.find('{')
        end = sanitized_message.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            json_str = sanitized_message[start:end+1]
            try:
                json_data = json.loads(json_str)
                return json_data
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                return {}
        else:
            print("No JSON found in the message")
            return {}

    async def write_code(self, input, new_code):
        return
        with open("comon.py", "r") as file:
            existing_code = file.read()
            response = model.chat.completions.create(
                model="gpt-4-0125-preview",
                messages=[
                    {
                        "role": "system",
                        "content": f"""
                        You are a python code writing agent.
                        Here is the code you have written so far:
                        {existing_code}
                        You will be given a comment and a code snippet to add to the code.
                        You will need to add the code snippet to the code and add the comment to the code.
                        If the comment describes a conditional statement (e.g. if conditions), then add the code await agent.chat(comment) instead of the code that the user has given you.
                        The number before the comment is the step number. You will need to add the comment and the code snippet to the code in the order of the step number.
                    """,
                    },
                    {
                        "role": "user",
                        "content": f"""
                        Here is the comment for this line of code that I want to add: "[{self.step_count}]. {input}"
                        Here is the code I want to add: {new_code}
                    """,
                    },
                ],
                max_tokens=4096,
            )
            message = response.choices[0].message
            message_text = message.content
            print("Code Assistant:", message_text)
            # replace the existing code with the message_text
            with open("comon.py", "w") as file:
                file.write(message_text)
            self.step_count += 1

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
                            "text": f"""Here's the screenshot of the website you are on right now.
                                \n{self.instructions}\n
                                Here's the text representation of the website:
                                \n{self.page_text}
                                """,
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
                except openai.RateLimitError as e:
                    print(
                        f"Rate limit exceeded, attempt {attempt + 1} of {3}. Retrying in {120} seconds..."
                    )
                    time.sleep(120)

            if not response:
                raise Exception("API call failed after retrying")

            message = response.choices[0].message
            message_text = message.content

            self.messages.append(
                {
                    "role": "assistant",
                    "content": message_text,
                }
            )

            self.messages = [self.messages[0]] + self.messages[-4:]

            print("Browser Assistant:", message_text)

            data = self.extract_json(message_text)
            try:
                if "click" in data:
                    id = int(data["click"])
                    elements = await self.page.query_selector_all(self.tag_to_xpath[id])
                    if elements:
                        await elements[0].click()
                        await self.write_code(
                            input,
                            f"""
                                await page.wait_for_selector('{self.tag_to_xpath[id]}')
                                elements = await page.query_selector_all('{self.tag_to_xpath[id]}')
                                if elements:
                                    await elements[0].click()
                                    await page.wait_for_timeout(2000)
                            """,
                        )
                    await self.process_page()
                    continue
                elif "url" in data:
                    url = data["url"]
                    await self.page.goto(url)
                    await self.write_code(
                        input, f"await page.goto('{url}', waitUntil='domcontentloaded')"
                    )
                    await self.process_page()
                    continue
                elif "input" in data:
                    id = int(data["input"]["select"])
                    text_to_type = data["input"]["text"]
                    elements = await self.page.query_selector_all(self.tag_to_xpath[id])
                    if elements:
                        await elements[0].fill("")
                        await self.page.wait_for_timeout(2000)
                        await elements[0].type(text_to_type)
                        await self.page.keyboard.press("Enter")
                        await self.write_code(
                            input,
                            f"""
                                await page.wait_for_selector('{self.tag_to_xpath[id]}')
                                elements = await page.query_selector_all('{self.tag_to_xpath[id]}')
                                if elements:
                                    await elements[0].type('{text_to_type}')
                                    await page.wait_for_timeout(2000)
                            """,
                        )
                    await self.process_page()
                    continue
                elif "keyboard" in data:
                    key = data["keyboard"]
                    await self.page.keyboard.press(key)
                    await self.write_code(
                        input,
                        f"""
                            await page.keyboard.press('{key}'
                            await page.wait_for_timeout(2000)
                        """,
                    )
                    await self.process_page()
                    continue
                elif "navigation" in data:
                    navigation = data["navigation"]
                    if navigation == "back":
                        await self.page.go_back()
                        await self.write_code(
                            input,
                            """
                                await page.go_back()
                                await page.wait_for_timeout(2000)
                            """,
                        )
                    elif navigation == "forward":
                        await self.page.go_forward()
                        await self.write_code(
                            input,
                            """
                                await page.go_forward()
                                await page.wait_for_timeout(2000)
                            """,
                        )
                    elif navigation == "reload":
                        await self.page.reload()
                        await self.write_code(
                            input,
                            """
                                await page.reload()
                                await page.wait_for_timeout(2000)
                            """,
                        )
                    await self.process_page()
                    continue
                elif "element not present" in data:
                    await self.write_code(
                        input,
                        f"""
                            await agent.chat(\"\"\"{input}\"\"\")
                        """,
                    )
                elif "record response" in data:
                    account = data["record response"]["account"]
                    email = data["record response"]["email"]
                    keyword = data["record response"]["keyword"]
                    question = data["record response"]["question"]
                    name = data["record response"]["name"]
                    response = data["record response"]["response"]
                    print(f"Recording response for {name}: {response}")
                    url = f"http://localhost:{port}/record-response"

                    data = {
                        "account": account,
                        "email": email,
                        "keyword": keyword,
                        "question": question,
                        "name": name,
                        "response": response,
                    }

                    response = requests.post(url, json=data)

                    print(response.status_code)
                    print(response.text)
                elif "record reachout" in data:
                    account = data["record reachout"]["account"]
                    email = data["record reachout"]["email"]
                    keyword = data["record reachout"]["keyword"]
                    question = data["record reachout"]["question"]
                    name = data["record reachout"]["name"]
                    print(
                        f"Recording reachout for name: {name}, email: {email}, keyword: {keyword}, question: {question}"
                    )
                    url = f"http://localhost:{port}/record-reachout"
                    data = {
                        "account": account,
                        "email": email,
                        "keyword": keyword,
                        "question": question,
                        "name": name,
                    }
                    response = requests.post(url, json=data)
                    print(response.status_code)
                    print(response.text)
                elif "delete reachout" in data:
                    account = data["delete reachout"]["account"]
                    email = data["delete reachout"]["email"]
                    keyword = data["delete reachout"]["keyword"]
                    question = data["delete reachout"]["question"]
                    name = data["delete reachout"]["name"]
                    print(
                        f"Deleting reachout for name: {name}, email: {email}, keyword: {keyword}, question: {question}"
                    )
                    url = f"http://localhost:{port}/delete-reachout"
                    data = {
                        "account": account,
                        "email": email,
                        "keyword": keyword,
                        "question": question,
                        "name": name,
                    }
                    response = requests.post(url, json=data)
                    print(response.status_code)
                    print(response.text)
            except TimeoutError as e:
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": f"TimeoutError occurred: {e}",
                    }
                )
                continue
            return message_text
