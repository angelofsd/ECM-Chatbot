#!/usr/bin/env python3
"""
ECM RAG Chatbot - Simplified FastAPI Backend
No ORM dependencies - direct Qdrant + OpenAI integration
"""

import os
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from openai import OpenAI

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# ========================
# Configuration
# ========================
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ecm_docs")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================
# Pydantic Models
# ========================
class Citation(BaseModel):
    filename: str
    citation_count: int
    order: int

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation] = []
    tokens_used: int = 0
    sources_count: int = 0
    model: str = "gpt-5-mini"

class HealthResponse(BaseModel):
    status: str
    timestamp: str

# ========================
# FastAPI App
# ========================
app = FastAPI(
    title="ECM RAG Chatbot API",
    description="Retrieval-Augmented Generation for ECM project documents",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================
# Utilities
# ========================
def search_documents(query: str, top_k: int = 5) -> List[dict]:
    """Search Qdrant for relevant documents."""
    try:
        # Create embedding for query
        client = OpenAI(api_key=OPENAI_API_KEY)
        embedding_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = embedding_response.data[0].embedding
        
        # Search Qdrant
        search_payload = {
            "vector": query_embedding,
            "limit": top_k,
            "with_payload": True
        }
        
        response = requests.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
            json=search_payload,
            timeout=10
        )
        response.raise_for_status()
        
        results = response.json().get('result', [])
        
        # Format results
        formatted_results = []
        for point in results:
            payload = point.get('payload', {})
            formatted_results.append({
                'filename': payload.get('filename', 'Unknown'),
                'text': payload.get('text', '')[:500],  # First 500 chars
                'score': point.get('score', 0)
            })
        
        return formatted_results
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

def generate_answer(query: str, search_results: List[dict]) -> tuple[str, List[Citation]]:
    """Generate answer using LLM with citations."""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Build context from search results
        context = ""
        citations = {}
        for i, result in enumerate(search_results, 1):
            filename = result['filename']
            text = result['text']
            context += f"\n[{i}] {filename}:\n{text}\n"
            if filename not in citations:
                citations[filename] = {'count': 0, 'order': i}
            citations[filename]['count'] += 1
        
        # Create prompt
        system_prompt = """You are an expert assistant for New Mexico Mutual's ECM (Enterprise Content Management) 
replacement project. Answer questions about the project using the provided documents. 
Always cite your sources by referring to the document numbers [1], [2], etc. 
Be accurate and concise."""
        
        user_message = f"""Context from project documents:
{context}

Question: {query}

Please provide a clear answer based on the documents above."""
        
        # Call LLM
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            # gpt-5-mini only supports default temperature=1
            max_completion_tokens=2048
        )
        
        answer = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        
        # Build citations list
        citation_list = [
            Citation(
                filename=filename,
                citation_count=data['count'],
                order=data['order']
            )
            for filename, data in citations.items()
        ]
        
        return answer, citation_list, tokens_used
    
    except Exception as e:
        logger.error(f"Answer generation error: {e}")
        raise

# ========================
# Routes
# ========================
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat()
    )

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """RAG query endpoint."""
    try:
        # Search for relevant documents
        search_results = search_documents(request.query, top_k=request.top_k)
        
        if not search_results:
            return QueryResponse(
                query=request.query,
                answer="I could not find relevant information in the documents to answer your question.",
                citations=[],
                tokens_used=0,
                sources_count=0,
                model="gpt-5-mini"
            )
        
        # Generate answer
        answer, citations, tokens_used = generate_answer(request.query, search_results)
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            citations=citations,
            tokens_used=tokens_used,
            sources_count=len(search_results),
            model="gpt-5-mini"
        )
    
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ECM RAG Chatbot API",
        "docs": "/docs",
        "health": "/health",
        "query": "/query"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
