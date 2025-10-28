"""
Configuration management for ECM RAG Chatbot API.

Loads settings from environment variables or uses sensible defaults.
All paths and credentials should be configured here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# ========================
# Database Configuration
# ========================
# Toggle between SQLite (local dev) and Postgres (production)
USE_SQLITE = os.getenv("USE_SQLITE", "true").lower() == "true"

if USE_SQLITE:
    # SQLite for local development (no Docker needed)
    SQLITE_PATH = Path(os.getenv("SQLITE_PATH", r"C:\ecm-staging\ecm_rag.db"))
    DATABASE_URL = f"sqlite:///{SQLITE_PATH}"
    DATABASE_URL_ASYNC = f"sqlite+aiosqlite:///{SQLITE_PATH}"
else:
    # Postgres for production
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "15432")  # Using non-standard port to avoid conflicts
    POSTGRES_DB = os.getenv("POSTGRES_DB", "ecm_rag")
    DATABASE_URL = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    DATABASE_URL_ASYNC = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# ========================
# Vector Store (Qdrant)
# ========================
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ecm_docs")

# ========================
# OCR & Document Paths
# ========================
OCR_OUTPUT_DIR = Path(os.getenv(
    "OCR_OUTPUT_DIR",
    r"C:\ecm-staging\04_text_ready"
))
INVENTORY_CSV = Path(os.getenv(
    "INVENTORY_CSV",
    r"C:\ecm-staging\inventory.csv"
))

# ========================
# Embedding Model
# ========================
# Option to use OpenAI embeddings (requires OPENAI_API_KEY)
USE_OPENAI_EMBEDDINGS = os.getenv("USE_OPENAI_EMBEDDINGS", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if USE_OPENAI_EMBEDDINGS:
    # OpenAI text-embedding-3-small (1536 dimensions, most cost-effective)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
else:
    # BGE small model (lightweight, local)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# ========================
# Chunking Parameters
# ========================
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # tokens (was 300)
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "75"))  # tokens (was 50)
CHUNK_LIMIT = int(os.getenv("CHUNK_LIMIT", "200"))

# ========================
# Ingestion Performance Tuning
# ========================
EMBEDDING_MINI_BATCH_SIZE = int(os.getenv("EMBEDDING_MINI_BATCH_SIZE", "40"))
EMBEDDING_API_BATCH_SIZE = int(os.getenv("EMBEDDING_API_BATCH_SIZE", "100"))

# ========================
# Retrieval Parameters
# ========================
SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "5"))
USE_RERANKER = os.getenv("USE_RERANKER", "true").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-12-v2")

# ========================
# LLM Configuration
# ========================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "local"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# ========================
# Security & Auth
# ========================
# Demo token for local testing (upgrade to Azure AD in production)
DEMO_USER_TOKEN = os.getenv("DEMO_USER_TOKEN", "demo-token-12345")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"

# ========================
# Logging
# ========================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ========================
# FastAPI
# ========================
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"
API_PORT = int(os.getenv("API_PORT", "8000"))

# ========================
# Validation
# ========================
def validate_config():
    """Validate critical configuration values."""
    errors = []
    
    if not OCR_OUTPUT_DIR.exists():
        errors.append(f"OCR_OUTPUT_DIR does not exist: {OCR_OUTPUT_DIR}")
    
    if not INVENTORY_CSV.parent.exists():
        errors.append(f"INVENTORY_CSV parent dir does not exist: {INVENTORY_CSV.parent}")
    
    # Could add database connectivity check here
    
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


if __name__ == "__main__":
    # Print config for debugging
    print("=== ECM RAG Chatbot Configuration ===")
    print(f"Database: {DATABASE_URL}")
    print(f"Qdrant: {QDRANT_URL} (collection: {QDRANT_COLLECTION})")
    print(f"OCR Output: {OCR_OUTPUT_DIR}")
    print(f"Embedding Model: {EMBEDDING_MODEL}")
    print(f"Chunk Size: {CHUNK_SIZE} tokens, Overlap: {CHUNK_OVERLAP}")
    print(f"Reranker: {USE_RERANKER} ({RERANKER_MODEL if USE_RERANKER else 'disabled'})")
    print(f"LLM: {LLM_PROVIDER.upper()} / {LLM_MODEL}")
    print(f"Auth Enabled: {AUTH_ENABLED}")
    print()
    is_valid = validate_config()
    print(f"Configuration Valid: {is_valid}")
