"""
FastAPI main application for ECM RAG Chatbot.

Endpoints:
  GET  /health              - Health check
  POST /ingest              - Ingest documents (admin only)
  POST /query               - RAG query (requires auth)

Middleware:
  - Authentication via bearer token
  - Logging of all requests
  - Error handling with proper HTTP status codes
"""

import logging
import time
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.config import DEBUG_MODE, API_PORT, LOG_LEVEL
from api.db import db
from api.security import AuthMiddleware, require_auth, get_user_from_request
from api.retriever import get_retriever

# ========================
# Logging Setup
# ========================

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ========================
# FastAPI App
# ========================

app = FastAPI(
    title="ECM RAG Chatbot API",
    description="Retrieval-Augmented Generation chatbot for ECM project documents",
    version="0.1.0",
    debug=DEBUG_MODE,
)

# ========================
# Middleware
# ========================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware for logging and auth
@app.middleware("http")
async def log_middleware(request: Request, call_next):
    """Log all requests and add timing."""
    start_time = time.time()
    
    # Try to attach user
    try:
        user = get_user_from_request(request)
        request.scope["user"] = user
        username = user.username
    except:
        username = "unknown"
    
    # Call endpoint
    response = await call_next(request)
    
    # Log
    duration = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"user={username} - "
        f"status={response.status_code} - "
        f"duration={duration:.2f}s"
    )
    
    return response


# ========================
# Request/Response Models
# ========================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class IngestRequest(BaseModel):
    """Ingest documents request."""
    collection: str = "ecm_docs"
    force_reindex: bool = False
    sample: Optional[int] = None


class IngestResponse(BaseModel):
    """Ingest response."""
    status: str
    message: str
    ingested_count: int
    failed_count: int


class QueryRequest(BaseModel):
    """RAG query request."""
    query: str
    top_k: int = 5
    use_reranker: bool = True


class Citation(BaseModel):
    """Citation for a source document."""
    filename: str
    citation_count: int = 1
    order: int = 0


class QueryResponse(BaseModel):
    """RAG query response."""
    query: str
    answer: str
    citations: list[Citation]
    tokens_used: int
    sources_count: int
    model: str


# ========================
# Routes
# ========================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )


@app.post("/ingest", response_model=IngestResponse, tags=["Admin"])
async def ingest(request: IngestRequest, current_user = Depends(require_auth)):
    """
    Ingest documents from OCR_OUTPUT_DIR into vector store and database.
    
    Requires: Admin role (currently disabled for demo)
    
    Args:
        request: IngestRequest with configuration
        current_user: Authenticated user
    
    Returns:
        IngestResponse with results
    """
    # TODO: Check if user is admin
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    logger.info(f"Ingest requested by {current_user.username}")
    
    try:
        # Import here to avoid circular imports
        from api.ingest_pdf import main as ingest_main
        
        # Run ingestion
        # Note: This is blocking - in production, use async task queue
        ingest_main(
            force_reindex=request.force_reindex,
            sample=request.sample,
        )
        
        return IngestResponse(
            status="success",
            message="Ingestion completed",
            ingested_count=0,  # TODO: Return actual counts
            failed_count=0,
        )
    
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return IngestResponse(
            status="error",
            message=str(e),
            ingested_count=0,
            failed_count=0,
        )


@app.post("/query", response_model=QueryResponse, tags=["RAG"])
async def query(request: QueryRequest, current_user = Depends(require_auth)):
    """
    Query the RAG system with LLM-generated answers.
    
    Requires: Authentication (any user)
    
    Args:
        request: QueryRequest with search terms
        current_user: Authenticated user
    
    Returns:
        QueryResponse with LLM-generated answer and citations
    """
    logger.info(f"Query from {current_user.username}: {request.query}")
    
    try:
        # Get retriever and answer generator
        from api.retriever import get_retriever
        from api.answer_generator import get_answer_generator
        
        retriever = get_retriever()
        answer_gen = get_answer_generator()
        
        # Perform hybrid search
        search_results = retriever.hybrid_search(
            query=request.query,
            user=current_user,
            top_k=request.top_k,
            use_reranker=request.use_reranker,
        )
        
        # Generate answer using LLM
        rag_result = answer_gen.generate(
            query=request.query,
            search_results=search_results,
            verbose=DEBUG_MODE,
        )
        
        # Convert citations to response format
        citations = [
            Citation(
                filename=c["filename"],
                citation_count=c["citation_count"],
                order=c["order"],
            )
            for c in rag_result.get("citations", [])
        ]
        
        return QueryResponse(
            query=request.query,
            answer=rag_result.get("answer", ""),
            citations=citations,
            tokens_used=rag_result.get("tokens_used", 0),
            sources_count=rag_result.get("sources_count", 0),
            model=rag_result.get("model", "unknown"),
        )
    
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ========================
# Error Handlers
# ========================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ========================
# Startup/Shutdown
# ========================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting ECM RAG Chatbot API...")
    
    # Initialize database
    db.init_sync()
    db.create_all_tables()
    logger.info("Database initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down ECM RAG Chatbot API...")


# ========================
# Main
# ========================

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on port {API_PORT}...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=DEBUG_MODE,
        log_level=LOG_LEVEL.lower(),
    )
