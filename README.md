# AI Fashion Designer 👗✨

Welcome to the AI Fashion Designer! This is a Vision-First RAG (Retrieval-Augmented Generation) backend service that takes the tedious work out of cataloging fashion items and makes them instantly searchable via natural language. 

Because let's face it, no one wants to manually type out "yellow and black embroidered saree for weddings" 500 times.

## What it does

1. **Look & Learn**: Feeds garment images to Google Gemini Pro Vision to automatically extract structured fashion metadata (category, color, occasion, style tags).
2. **Remember**: Embeds this metadata using OpenAI's `text-embedding-3-small` and stores it into Pinecone.
3. **Find**: Lets you search for clothes simply by describing them. Ask for "something elegant for a party" and the app will do the heavy lifting.

All of this works without you ever touching a CSV file. You're welcome.

## Tech Stack

- **FastAPI** (Python) for the speedy API and Swagger UI.
- **Google Gemini Pro Vision** for looking at the clothes.
- **OpenAI** for turning text into 1536-dimensional math arrays.
- **Pinecone** for stashing and querying said arrays.

## Setup & Run

1. Clone this repository.
2. Setup your virtual environment and install the required packages:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your API keys (Gemini, OpenAI, Pinecone, plus your own app secret). We promise we won't peek.
4. Run the FastAPI server:
   ```bash
   uvicorn src.main:app --reload
   ```
5. Head over to `http://127.0.0.1:8000/docs` to test the API via Swagger UI.

## Typical API Flow

- **`POST /v1/ingest/start`**: Kick off the ingestion process.
- **`GET /v1/ingest/status/{job_id}`**: Check if the ingestion job is done.
- **`POST /v1/search`**: Search for items using natural language (e.g., "red dress for a summer party"). Supports both soft semantic search and strict filtering modes.
- **`GET /v1/health`**: To check if our AI designer hasn't fallen asleep at its desk.

## Roadmap

This is Phase I. We're keeping it simple, clean, and scalable. In Phase II, we plan to add support for extended metadata extraction, a PostgreSQL database, and even outfit composition.

---
*Built with ❤️, Python, and a whole lot of vectors.*
