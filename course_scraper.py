import os
# Set gRPC environment variables BEFORE any other imports
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_TRACE"] = "none"

# Optional: if you don't need absl logging, you can comment these out:
# import absl.logging
# absl.logging.set_verbosity(absl.logging.ERROR)

import sys
import pathlib
import re
from typing import List, Any
import time
from io import BytesIO
import logging

from dotenv import load_dotenv
from bs4 import BeautifulSoup
import chainlit as cl
from openai import OpenAI
import requests
import PyPDF2

# Set up environment variables and directories for Chainlit files
os.environ['CHAINLIT_FILES_DIRECTORY'] = '/tmp/.files'
pathlib.Path('/tmp/.files').mkdir(parents=True, exist_ok=True)
sys.path.append('/tmp/.files')

# Load environment variables from the .env file
load_dotenv(dotenv_path="/Users/brandono/Projects/DataQualityProject/.env")

# Initialize OpenAI client using the key from .env
api_key: str = os.getenv('OPENAI_API_KEY')
if not api_key or api_key == "sk-12345***********************cdef":
    raise ValueError("Please set a valid OPENAI_API_KEY in your .env file.")
client: OpenAI = OpenAI(api_key=api_key)

# Global state variables for conversation flow
user_input: str = ""
resume_input: str = ""
time_input: str = ""
search_keywords: List[str] = []
state: str = "awaiting_situation"  # states: awaiting_situation, awaiting_resume, awaiting_learning_time, awaiting_keywords

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("LearningModuleApp")

#####################
# Utility Functions #
#####################

def timed_function(func, *args, **kwargs):
    start = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start
    print(f"{func.__name__} took {elapsed:.2f} seconds")
    return result, elapsed

##########################
# PDF Processing Helpers #
##########################

def process_resume_pdf(file: Any) -> str:
    with open(file.path, "rb") as f:
        pdf_reader = PyPDF2.PdfReader(f)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_resume_skills(text: str) -> str:
    match = re.search(r"(?i)(?:Key Skills|Skills)[:\s]*(.*?)(\n{2,}|\Z)", text, re.DOTALL)
    if match:
        skills = match.group(1).strip()
        return skills
    else:
        return "No skills section found. Please ensure your resume includes a 'Skills' section."

#####################
# Core Functions    #
#####################

def generate_learning_module(user_situation: str, skills: str, learning_time: str) -> str:
    prompt: str = (
        f"User situation: {user_situation}\n"
        f"Skills and experience (from resume): {skills}\n"
        f"Time dedicated to learning: {learning_time} hours\n\n"
        "Generate a detailed learning module outline for the week, including key topics, resources, exercises, "
        "and an approximate time estimate for each section. Provide a final estimated total time for the module generation."
    )
    response: Any = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates learning modules."},
            {"role": "user", "content": prompt},
        ],
    )
    module: str = response.choices[0].message.content.strip()
    return module

def generate_test_product(user_situation: str, skills: str) -> str:
    prompt: str = (
        f"User situation: {user_situation}\n"
        f"Skills and experience (from resume): {skills}\n\n"
        "Generate a creative project or product idea that the user can build to test their knowledge of DuckDB and "
        "database API design. Describe the idea and outline the key steps."
    )
    response: Any = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates project ideas."},
            {"role": "user", "content": prompt},
        ],
    )
    product: str = response.choices[0].message.content.strip()
    return product

def search_youtube_videos(query: str, max_results: int = 5) -> List[str]:
    """
    Scrape YouTube search results using ScraperAPI and return a list of video URLs.
    """
    scraper_api_key = os.getenv("SCRAPER_API_KEY") or "default-scraper-api-key"
    base_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    params = {
        "api_key": scraper_api_key,
        "url": base_url,
        "render": "true"
    }
    response = requests.get("https://api.scraperapi.com", params=params)
    if response.status_code != 200:
        print("Failed to retrieve the page:", response.status_code)
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    video_urls: List[str] = []
    video_tags = soup.find_all("a", {"id": "video-title"})
    if not video_tags:
        print("No video tags with id 'video-title' found.")
    for tag in video_tags:
        link = tag.get("href")
        if link:
            full_link = f"https://www.youtube.com{link}"
            if full_link not in video_urls:
                video_urls.append(full_link)
            if len(video_urls) >= max_results:
                break
    if not video_urls:
        print("No video URLs found with current selectors.")
    return video_urls

#####################
# Chainlit Events   #
#####################

@cl.on_chat_start
async def start_chat() -> None:
    print("State: awaiting_situation")
    await cl.Message(content="Welcome! Please describe your current situation.").send()

@cl.on_message
async def on_message(msg: cl.Message) -> None:
    global user_input, resume_input, time_input, search_keywords, state

    if state == "awaiting_situation":
        user_input = msg.content.strip()
        print(f"Received situation: {user_input}")
        state = "awaiting_resume"
        files = await cl.AskFileMessage(
            content="Thank you for sharing your situation. Please upload your resume as a PDF file (ensure it includes a 'Skills' section).",
            accept=["application/pdf"],
            timeout=120
        ).send()
        if files is None or len(files) == 0:
            await cl.Message(content="Resume upload timed out. Please try again.").send()
            return
        file = files[0]
        resume_text = process_resume_pdf(file)
        skills = extract_resume_skills(resume_text)
        resume_input = skills
        await cl.Message(content=f"Resume uploaded successfully. Extracted skills: {skills}").send()
        state = "awaiting_learning_time"
        print("State advanced to awaiting_learning_time")
        await cl.Message(content="Now, please enter the number of hours you can dedicate to learning this week (e.g., 1 hour, 2 hours, etc.).").send()
        return

    elif state == "awaiting_learning_time":
        time_input = msg.content.strip()
        print(f"Received learning time: {time_input}")
        state = "awaiting_keywords"
        await cl.Message(content="Great! Now, please provide the top two search keywords you'd like to know more about (separated by a comma).").send()
        return

    elif state == "awaiting_keywords":
        search_keywords = [kw.strip() for kw in msg.content.split(",")][:2]
        print(f"Received keywords: {search_keywords}")
        await cl.Message(content="All set! Generating your learning module now...").send()

        # Generate learning module with timing feedback
        module, module_time = timed_function(generate_learning_module, user_input, resume_input, time_input)
        await cl.Message(content=f"Here is your learning module (generated in {module_time:.2f} seconds):\n\n{module}").send()

        # Generate test product with timing feedback
        await cl.Message(content="Generating a project idea to test your knowledge...").send()
        product, product_time = timed_function(generate_test_product, user_input, resume_input)
        await cl.Message(content=f"Here is a project idea (generated in {product_time:.2f} seconds):\n\n{product}").send()

        # Search for YouTube videos based on the keywords
        await cl.Message(content="Searching YouTube for relevant videos...").send()
        videos_result: List[str] = []
        for keyword in search_keywords:
            results = search_youtube_videos(query=keyword, max_results=5)
            videos_result.extend(results)
        
        # Display clickable video links and an inline video preview if available
        if videos_result:
            video_links: str = "\n".join(
                [f"[Video {i+1}]({url})" for i, url in enumerate(videos_result[:5])]
            )
            await cl.Message(content=f"Here are the top 5 YouTube videos as links:\n\n{video_links}").send()
            
            video_element = cl.Video(
                name="Example Video",
                url=videos_result[0],
                display="inline"
            )
            await cl.Message(
                content="Here is an example video displayed inline:",
                elements=[video_element]
            ).send()
        else:
            await cl.Message(content="No applicable YouTube videos found for the given keywords.").send()

        # Reset state for the next session
        user_input, resume_input, time_input, search_keywords = "", "", "", []
        state = "awaiting_situation"
        print("State reset to awaiting_situation")
        return

    else:
        await cl.Message(content="Please follow the instructions provided.").send()
