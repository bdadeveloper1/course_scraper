#!/usr/bin/env python3
"""
CiviHire – A Chainlit-based module for transforming job descriptions for HR professionals.
This production-grade code is designed to be robust, extendable, and efficient.
It demonstrates how to combine a user-uploaded job description with HR intentions to generate
an AI-enhanced job description, while also returning similar jobs from an aggregated synthetic dataset.
Additionally, if the user requests a chart/diagram/statistics, it generates a quick growth chart.
It also uses OpenAI embeddings to perform a cosine-similarity search for better job matching.
"""

###############################################################################
# ENVIRONMENT SETUP & IMPORTS
###############################################################################
import os
import sys
import pathlib
import re
import time
import asyncio
import logging
import random
from functools import wraps
from typing import List, Optional, Protocol, Callable, TypeVar, TypedDict

import pandas as pd
import chainlit as cl
import plotly.express as px
import pickle
import unicodedata
from chainlit import Pdf
from fpdf import FPDF
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
import requests

# Chainlit and OpenAI imports
from chainlit import (
    on_chat_start,
    on_message,
    Message,
    AskFileMessage,
    user_session,
    Image
)
from openai import OpenAI

# Set up Chainlit files directory
os.environ["CHAINLIT_FILES_DIRECTORY"] = "/tmp/.files"
pathlib.Path("/tmp/.files").mkdir(parents=True, exist_ok=True)
sys.path.append("/tmp/.files")

# Load environment variables
load_dotenv(dotenv_path="/Users/brandono/Projects/DataQualityProject/.env")

###############################################################################
# CLIENT & LOGGING SETUP
###############################################################################
api_key: str = os.getenv("OPENAI_API_KEY") or ""
if not api_key or api_key == "sk-12345***********************cdef":
    raise ValueError("Please set a valid OPENAI_API_KEY in your .env file.")

client: OpenAI = OpenAI(api_key=api_key)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("CiviHireApp")

###############################################################################
# TYPE DEFINITIONS
###############################################################################
class FileWithPath(Protocol):
    """Protocol for file-like objects that have a 'path' attribute."""
    path: str

class ChatMessageDict(TypedDict):
    role: str
    content: str

class ChatChoiceDict(TypedDict):
    message: ChatMessageDict

class ChatResponseDict(TypedDict):
    choices: List[ChatChoiceDict]

###############################################################################
# UTILITY DECORATORS
###############################################################################
T = TypeVar("T")
def timed(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to measure the execution time of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"{func.__name__} took {elapsed:.2f} seconds")
        return result
    return wrapper

###############################################################################
# PDF PROCESSING HELPERS (for job description upload)
###############################################################################
@timed
def process_job_description_pdf(file: FileWithPath) -> str:
    """Extract text from a PDF job description with robust error handling."""
    try:
        with open(file.path, "rb") as f:
            pdf_reader = PdfReader(f)
            if pdf_reader.is_encrypted:
                try:
                    pdf_reader.decrypt("")
                except NotImplementedError:
                    raise ValueError("Encrypted PDF - unable to decrypt")
            text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
            return text
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File {file.path} not found") from e
    except PdfReadError as e:
        raise ValueError("Invalid or corrupted PDF") from e

@timed
def extract_job_skills(text: str) -> str:
    """Extract key skills from job description text using regex pattern matching."""
    pattern = re.compile(
        r"(?i)(?:key\s*skills|technical\s*skills|core\s*competencies|skills?)[:\s\-]*"
        r"(.*?)(?:\n\s*\n|(?=\n\s*(?:Responsibilities|Requirements|Qualifications))|\Z)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return "No skills section found."
    skills_text = match.group(1).strip()
    if not skills_text:
        return "Skills section found but empty."
    skills_text = re.sub(r"\s+", " ", skills_text)
    skills_text = re.sub(r"([,•|])+", r"\1", skills_text)
    return skills_text

###############################################################################
# GLOBAL: LOAD SYNTHETIC HR JOB DATASET
###############################################################################
CSV_PATH = "/Users/brandono/Documents/course_scrape/synthetic_hr_jobs.csv"
try:
    jobs_df = pd.read_csv(CSV_PATH)
    logger.info("Loaded synthetic HR jobs dataset with %d rows", len(jobs_df))
except Exception as e:
    logger.error("Failed to load CSV dataset: %s", str(e))
    jobs_df = pd.DataFrame()  # fallback to empty dataframe

###############################################################################
# OPENAI EMBEDDING & SIMILARITY FUNCTIONS
###############################################################################
def embed_text(text: str) -> List[float]:
    """
    Use OpenAI's embedding API to convert text into a vector.
    """
    response = client.embeddings.create(input=[text], model="text-embedding-ada-002")
    response_dict = response.to_dict()  # Convert to dictionary
    return response_dict["data"][0]["embedding"]

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)

def perform_enhanced_similarity_search(query: str) -> str:
    """
    Return formatted markdown with proper line breaks (using '  ' for markdown newlines)
    """
    if jobs_df.empty or "embedding" not in jobs_df.columns:
        return "No comparable job data available in our system."
    
    query_vector = embed_text(query)
    scores = []
    for idx, row in jobs_df.iterrows():
        job_vector = row["embedding"]
        score = cosine_similarity(query_vector, job_vector)
        scores.append(score)
    
    jobs_df["similarity_score"] = scores
    sorted_jobs = jobs_df.sort_values(by="similarity_score", ascending=False).head(3)
    
    results = []
    for idx, row in sorted_jobs.iterrows():
        result = (
            f"**{row['job_title']}**  \n"  # Double space for markdown line break
            f"- Agency: {row['agency_name']} ({row['agency_level']})  \n"
            f"- Location: {row['location']}  \n"
            f"- Salary: ${row['min_salary']} - ${row['max_salary']}  \n"
            f"- Posted: {row['posted_date']}  \n"
            f"- Work Type: {row['work_type']}  \n"
            f"- Match Score: {row['similarity_score']:.2f}  \n"
            f"**Key Skills:** {row['required_skills']}"
        )
        results.append(result)
    return "\n\n".join(results)

def generate_modified_job_description(original_desc: str, intentions: str) -> str:
    """
    Use OpenAI's GPT-4 to generate a modernized job description based on the original text
    and the HR's change intentions.
    """
    # Truncate the original description to, say, 1000 characters for speed and token efficiency.
    truncated_desc = original_desc if len(original_desc) <= 1000 else original_desc[:1000] + "..."
    
    prompt = (
        f"Original Job Description:\n{truncated_desc}\n\n"
        f"HR Intentions for Change:\n{intentions}\n\n"
        "Rewrite the job description to be modern, clear, and attractive for today's public sector candidates. "
        "Incorporate the requested changes, update language to be inclusive and tech-forward, and provide a concise, "
        "professional version."
    )
    logger.info("Sending GPT prompt for job description generation: %s", prompt)
    response = client.chat.completions.create(
        model="gpt-4-turbo",  # or use "gpt-3.5-turbo" for faster responses
        messages=[
            {"role": "system", "content": "You are a professional HR assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1000
    )
    generated_desc = response.choices[0].message.content.strip()
    logger.info("Generated job description: %s", generated_desc)
    return generated_desc


###############################################################################
# EMBEDDINGS CACHE FOR SYNTHETIC DATA
###############################################################################
EMBEDDINGS_CACHE_PATH = "/tmp/synthetic_hr_jobs_embeddings.pkl"

def precompute_dataset_embeddings(limit: int = 25) -> None:
    if jobs_df.empty:
        logger.error("No job data to precompute embeddings.")
        return

    if os.path.exists(EMBEDDINGS_CACHE_PATH):
        with open(EMBEDDINGS_CACHE_PATH, "rb") as f:
            cached_embeddings = pickle.load(f)
        if len(cached_embeddings) == len(jobs_df):
            jobs_df["embedding"] = cached_embeddings
            logger.info("Loaded cached embeddings for the synthetic dataset.")
            return

    embeddings = []
    logger.info("Precomputing embeddings for first %d of %d job descriptions...", limit, len(jobs_df))
    for idx, row in jobs_df.iterrows():
        if idx < limit:
            job_desc = row.get("description", "")
            if job_desc:
                embedding = embed_text(job_desc)
            else:
                embedding = [0.0] * 768
            embeddings.append(embedding)
        else:
            embeddings.append([0.0] * 768)
    
    jobs_df["embedding"] = embeddings
    with open(EMBEDDINGS_CACHE_PATH, "wb") as f:
        pickle.dump(embeddings, f)
    logger.info("Cached embeddings for the synthetic dataset (first %d computed).", limit)

precompute_dataset_embeddings(limit=25)



###############################################################################
# GROWTH CHART FUNCTION
###############################################################################
def generate_growth_chart(job_title: str) -> str:
    """
    Generate a growth chart showing the number of job postings per year for the specified job title.
    The chart is saved as a PNG image in a temporary location.
    """
    if jobs_df.empty:
        logger.error("No job data to generate chart.")
        return ""
    subset = jobs_df[jobs_df["job_title"].str.contains(job_title, case=False, na=False)].copy()
    if subset.empty:
        subset = jobs_df.copy()  # Fallback to entire dataset
    try:
        subset["posted_date"] = pd.to_datetime(subset["posted_date"], errors="coerce")
        subset = subset.dropna(subset=["posted_date"])
        subset["year"] = subset["posted_date"].dt.year
        count_by_year = subset.groupby("year").size().reset_index(name="job_count")
        fig = px.line(count_by_year, x="year", y="job_count", markers=True,
                      title=f"Job Postings Growth for '{job_title}'")
        temp_file = "/tmp/growth_chart.png"
        fig.write_image(temp_file)
        logger.info("Growth chart generated for job title: %s", job_title)
        return temp_file
    except Exception as e:
        logger.error("Error generating growth chart: %s", str(e))
        return ""

def safe_text(text: str) -> str:
    """
    Normalize text to remove non-ASCII characters.
    This will replace curly quotes and other unsupported characters.
    """
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')


def generate_job_pdf(job_desc: str) -> str:
    """
    Generate a PDF file from the job description text.
    Returns the path to the generated PDF.
    """
    # Clean the job description text using safe_text
    safe_job_desc = safe_text(job_desc)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, safe_job_desc)
    pdf_path = "/Users/brandono/Documents/course_scrape/public/job_description.pdf"
    pdf.output(pdf_path)
    return pdf_path


###############################################################################
# CHAINLIT EVENT HANDLERS & STATE
###############################################################################
class ChatState:
    """Encapsulates the per-user conversation state."""
    def __init__(self) -> None:
        self.job_situation: Optional[str] = None
        self.job_description: Optional[str] = None
        self.skills: Optional[str] = None
        self.intentions: Optional[str] = None

def chunk_user_input(user_input: str) -> str:
    """Return the last few words to avoid repetition."""
    words = user_input.strip().split()
    return " ".join(words[-5:]) if len(words) > 5 else user_input

def get_random_greeting() -> str:
    """Return a random, encouraging phrase."""
    greetings = [
        "Splendid!",
        "Excellent choice!",
        "That’s fantastic!",
        "Superb idea!",
        "Awesome!",
        "Great news!"
    ]
    return random.choice(greetings)

@on_chat_start
async def start_chat() -> None:
    """Initialize the session state and greet the user."""
    logger.info("Chat started; initializing session state.")
    user_session.set("state", ChatState())
    await cl.Message(
        content=(
            "👋 Welcome to **CiviHire** for HR professionals!\n"
            "I'm here to help you transform your existing job descriptions into modern, effective postings.\n"
            "To start, please tell me about the job role you're looking to enhance. For example:\n"
            "'We're hiring a data engineer for our public safety department to help fight wildfires in California.'"
        )
    ).send()

@on_message
async def handle_message(msg: Message) -> None:
    """
    Main event handler that guides the user through:
      1. Describing the job role situation.
      2. Uploading a job description (PDF).
      3. Specifying intentions for change.
      4. Generating a modernized job description.
      5. Returning similar job postings from our aggregated dataset.
      6. Optionally, generating a growth chart if requested.
    """
    logger.info("Received message: '%s'", msg.content)
    state: ChatState = user_session.get("state")

    # Check if the message is a request for a chart/diagram/statistics.
    if state.job_situation and state.job_description and state.intentions:
        if any(keyword in msg.content.lower() for keyword in ["chart", "diagram", "statistics", "growth", "vacancy"]):
            await handle_chart_request(state, msg)
            return

    try:
        if not state.job_situation:
            await handle_job_situation(state, msg)
        elif not state.job_description:
            logger.info("Job situation recorded. Prompting for job description upload.")
            await handle_job_description_prompt()
        elif not state.intentions:
            await handle_intentions(state, msg)
        else:
            await handle_output(state, msg)
    except Exception as e:
        logger.error("Error in handle_message: %s", str(e))
        await Message(content=f"⚠️ Error: {str(e)}").send()
        await reset_conversation()

async def handle_job_situation(state: ChatState, msg: Message) -> None:
    """Capture the HR's job situation input and prompt for job description upload."""
    user_input = msg.content.strip()
    if len(user_input) < 10:
        await Message(content="Please provide a bit more detail (at least 10 characters).").send()
        return

    state.job_situation = user_input
    chunked_input = chunk_user_input(user_input)
    greeting = get_random_greeting()
    logger.info("Job situation set to: %s", state.job_situation)
    await cl.Message(
        content=(
            f"{greeting} I understand you're looking to enhance a job description for **{chunked_input}**.\n"
            "Now, please upload the current job description as a PDF (this can be an existing posting or a document with buzzwords)."
        )
    ).send()
    await handle_job_description_prompt()

async def handle_job_description_prompt() -> None:
    """Prompt the user to upload the job description PDF."""
    logger.info("Prompting user with AskFileMessage for PDF job description.")
    files = await AskFileMessage(
        content="📎 Please upload the job description (PDF format).",
        accept=["application/pdf"],
        timeout=300
    ).send()
    if not files:
        await cl.Message(content="⌛ Upload timed out. Please try again.").send()
        return
    await handle_job_description_upload(files[0])

async def handle_job_description_upload(file: FileWithPath) -> None:
    """Process the uploaded job description PDF."""
    state: ChatState = user_session.get("state")
    logger.info("Processing job description file: %s", file.path)
    await cl.Message(content="⏳ Processing job description...").send()
    for progress in [25, 50, 75]:
        await asyncio.sleep(0.4)
        logger.info(f"Progress: {progress}% complete")
    logger.info("Progress: 100% complete")
    
    loop = asyncio.get_event_loop()
    try:
        job_text = await loop.run_in_executor(None, lambda: process_job_description_pdf(file))
        state.job_description = job_text
        snippet = job_text[:200] + "..." if len(job_text) > 200 else job_text
        skills = await loop.run_in_executor(None, lambda: extract_job_skills(job_text))
        state.skills = skills
        logger.info("Job description processed. Skills detected: %s", skills)
        await cl.Message(
            content=(
                f"✅ Job description processed successfully!\n\n"
                f"**Snippet:** {snippet}\n\n"
                f"**Detected Skills:** {skills}\n\n"
                "Now, please tell me what changes you'd like to make to this job posting. "
                "For example: 'Enhance it with the latest data processing tools, modernize language, and update education requirements.'"
            )
        ).send()
    except Exception as e:
        logger.error("Job description processing failed: %s", str(e))
        await cl.Message(
            content=(
                f"❌ Processing failed: {str(e)}\n\n"
                "Please try uploading your PDF again."
            )
        ).send()
        await handle_job_description_prompt()

async def handle_intentions(state: ChatState, msg: Message) -> None:
    """Capture the HR's intentions for how to modify the job description."""
    intentions_input = msg.content.strip()
    if len(intentions_input) < 5:
        await Message(content="Please provide more detail about what changes you want.").send()
        return
    state.intentions = intentions_input
    logger.info("Intentions set to: %s", state.intentions)
    await cl.Message(
        content=(
            "Great! I'm now generating an improved job description based on your input...\n"
            "Please hold on for a moment."
        )
    ).send()
    await handle_output(state, msg)

async def handle_output(state: ChatState, msg: cl.Message) -> None:
    try:
        new_job_desc = generate_modified_job_description(
            state.job_description or "", state.intentions or ""
        )
        similar_jobs = perform_enhanced_similarity_search(state.job_situation or "")
        
        # Generate the PDF and ensure it's saved in the CHAINLIT_FILES_DIRECTORY
        pdf_path = generate_job_pdf(new_job_desc)
        
        # Send the PDF preview first
        await cl.Message(
            content="✅ Here's your **Transformed Job Description** as a PDF:",
            elements=[cl.Pdf(name="Job Description", display="inline", path=pdf_path, page=1)]
        ).send()
        
        # Optionally, wait a short moment before sending the next message
        await asyncio.sleep(1)
        
        # Then send the text-based job description and similar jobs
        await cl.Message(
            content=(
                f"🧠 Based on your input, here are **3 similar job postings** from our dataset:\n\n{similar_jobs}\n\n"
                f"**Transformed Job Description:**\n\n{new_job_desc}"
            )
        ).send()

        await cl.Message(
            content="📊 You can type `make me a chart` to view job growth statistics!"
        ).send()

        logger.info("Successfully sent PDF preview, job description, and similar jobs to user.")
    except Exception as e:
        logger.error("Error generating output: %s", str(e))
        await cl.Message(content=f"⚠️ Error generating output: {str(e)}").send()
        await reset_conversation()



async def handle_chart_request(state: ChatState, msg: Message) -> None:
    """
    Handle requests for charts/diagrams/statistics. Generate a growth chart
    showing job posting counts over time for the relevant job title.
    """
    # For demo, try to extract a job title from the job situation.
    job_title = ""
    if "data engineer" in state.job_situation.lower():
        job_title = "Data Engineer"
    else:
        # Fallback: use the first two words of the job situation.
        job_title = " ".join(state.job_situation.split()[:2])
    
    logger.info("Generating growth chart for job title: %s", job_title)
    chart_path = generate_growth_chart(job_title)
    if chart_path:
        await Message(
            content=f"Here is the growth chart for job postings related to '{job_title}':",
            elements=[Image(name="Growth Chart", path=chart_path)]
        ).send()
    else:
        await Message(content="⚠️ Unable to generate growth chart at this time.").send()

async def reset_conversation() -> None:
    """Reset conversation state and restart dialogue if needed."""
    logger.info("Resetting conversation state.")
    user_session.set("state", ChatState())
    await start_chat()
