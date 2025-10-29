"""
Postgres database schema and ORM models for ECM RAG Chatbot.

Tables:
  - users: User profiles with department/role
  - documents: PDF metadata and indexing status
  - chunks: Text chunks with embeddings and parent document reference
  - acl_rules: Define which users/departments can access which documents

Uses SQLAlchemy ORM with async support.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Text, JSON, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from api.config import DATABASE_URL, DATABASE_URL_ASYNC, LOG_LEVEL

import logging

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

Base = declarative_base()

# ========================
# ORM Models
# ========================

class User(Base):
    """User profile with department/role information."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)  # e.g., "Claims", "Underwriting"
    role = Column(String(50), nullable=True)  # e.g., "admin", "user", "viewer"
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    acl_rules = relationship("ACLRule", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', dept='{self.department}')>"


class Document(Base):
    """Document metadata and indexing status."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    filename = Column(String(500), nullable=False)
    source_path = Column(String(1000), unique=True, nullable=False)
    relative_path = Column(String(1000), nullable=False)
    
    # Source type (pdf, email, word, etc.)
    source_type = Column(String(50), default="pdf")
    
    # File metadata
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=True, unique=False)  # Optional, not unique
    last_modified = Column(DateTime, nullable=True)
    
    # OCR info
    needs_ocr = Column(Boolean, default=False)
    ocr_status = Column(String(20), default="pending")  # pending, completed, failed
    
    # Indexing info
    indexed = Column(Boolean, default=False)
    indexed_at = Column(DateTime, nullable=True)
    chunk_count = Column(Integer, default=0)
    
    # Metadata
    department = Column(String(100), nullable=True)  # Guessed from path
    acl_tags = Column(Text, nullable=True)  # JSON or CSV of allowed departments
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    acl_rules = relationship("ACLRule", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', dept='{self.department}')>"


class Chunk(Base):
    """Text chunk with embedding from a document."""
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    
    # Content
    text = Column(Text, nullable=False)
    sequence = Column(Integer, nullable=False)  # Order within document
    
    # Embedding (stored as list in JSON or separate table)
    # For now, storing embedding vector ID from Qdrant
    qdrant_id = Column(String(256), nullable=True)  # Qdrant point ID
    
    # Metadata for search
    token_count = Column(Integer, nullable=True)
    similarity_score = Column(Float, nullable=True)  # For relevance feedback
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk(id={self.id}, doc_id={self.document_id}, seq={self.sequence})>"


class ACLRule(Base):
    """Access Control List: which users/departments can access which documents."""
    __tablename__ = "acl_rules"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    
    # ACL can be per-user or per-department
    department = Column(String(100), nullable=True)
    
    # Permissions
    can_view = Column(Boolean, default=True)
    can_download = Column(Boolean, default=False)
    can_cite = Column(Boolean, default=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="acl_rules")
    document = relationship("Document", back_populates="acl_rules")

    def __repr__(self):
        return (
            f"<ACLRule(id={self.id}, user_id={self.user_id}, "
            f"doc_id={self.document_id}, dept='{self.department}')>"
        )


# ========================
# Database Connection & Session Management
# ========================

class DatabaseManager:
    """Manages database connections and session creation."""

    def __init__(self, async_mode: bool = True):
        """
        Initialize database manager.
        
        Args:
            async_mode: If True, use async SQLAlchemy; else use sync
        """
        self.async_mode = async_mode
        self.engine = None
        self.session_factory = None

    def init_sync(self):
        """Initialize synchronous database."""
        self.engine = create_engine(DATABASE_URL, echo=False)
        self.session_factory = sessionmaker(bind=self.engine)
        logger.info(f"Initialized sync database: {DATABASE_URL}")

    async def init_async(self):
        """Initialize asynchronous database."""
        self.engine = create_async_engine(DATABASE_URL_ASYNC, echo=False)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        logger.info(f"Initialized async database: {DATABASE_URL_ASYNC}")

    def get_session(self):
        """Get a synchronous database session."""
        if not self.session_factory:
            self.init_sync()
        return self.session_factory()

    async def get_async_session(self):
        """Get an asynchronous database session."""
        if not self.session_factory:
            await self.init_async()
        return self.session_factory()

    def create_all_tables(self):
        """Create all tables in the database (sync)."""
        if not self.engine:
            self.init_sync()
        Base.metadata.create_all(self.engine)
        logger.info("Created all database tables")

    async def create_all_tables_async(self):
        """Create all tables in the database (async)."""
        if not self.engine:
            await self.init_async()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Created all database tables (async)")

    def drop_all_tables(self):
        """Drop all tables (careful!)."""
        if not self.engine:
            self.init_sync()
        Base.metadata.drop_all(self.engine)
        logger.warning("Dropped all database tables")


# ========================
# Global Database Manager Instance
# ========================

db = DatabaseManager(async_mode=False)


# ========================
# Helper Functions
# ========================

def get_or_create_user(username: str, email: str, department: str = None) -> User:
    """Get or create a user."""
    session = db.get_session()
    user = session.query(User).filter_by(username=username).first()
    if not user:
        user = User(username=username, email=email, department=department)
        session.add(user)
        session.commit()
        logger.info(f"Created new user: {username}")
    session.close()
    return user


def add_document(
    filename: str,
    source_path: str,
    relative_path: str,
    size_bytes: int,
    sha256: str,
    department: str = None,
    acl_tags: str = None,
    source_type: str = "pdf",
) -> int:
    """Add a new document and return its ID."""
    session = db.get_session()
    doc = Document(
        filename=filename,
        source_path=source_path,
        relative_path=relative_path,
        size_bytes=size_bytes,
        sha256=sha256,
        department=department,
        acl_tags=acl_tags,
        source_type=source_type,
    )
    session.add(doc)
    session.commit()
    # Get the ID before closing session
    doc_id = doc.id
    session.close()
    logger.info(f"Added document: {filename} (ID: {doc_id})")
    return doc_id  # Return ID instead of detached object


def add_chunk(document_id: int, text: str, sequence: int, qdrant_id: str = None) -> Chunk:
    """Add a text chunk."""
    session = db.get_session()
    chunk = Chunk(
        document_id=document_id,
        text=text,
        sequence=sequence,
        qdrant_id=qdrant_id,
        token_count=len(text.split()),
    )
    session.add(chunk)
    session.commit()
    session.close()
    return chunk


def get_user_accessible_documents(user: User) -> list:
    """Get documents accessible to a user (based on department)."""
    session = db.get_session()
    
    # Simple logic: user can access docs in their department
    # Could be expanded with explicit ACL rules
    docs = session.query(Document).filter(
        (Document.department == user.department) |
        (Document.acl_tags.contains(user.department))
    ).all()
    
    session.close()
    return docs


if __name__ == "__main__":
    # Initialize database and create tables
    print("Initializing database...")
    db.init_sync()
    db.create_all_tables()
    print("Done!")
