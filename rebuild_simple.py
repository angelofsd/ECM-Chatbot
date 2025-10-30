#!/usr/bin/env python3
"""
Simple rebuild script using direct psycopg2 (avoids SQLAlchemy session issues).
"""
import os
import psycopg2
from dotenv import load_dotenv
load_dotenv(override=True)

os.environ["USE_OPENAI_EMBEDDINGS"] = "true"

from api.embeddings import get_embedding_generator
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def rebuild_vectors_simple():
    """Simple bulk rebuild using psycopg2 directly."""
    
    # Connect to Postgres with direct psycopg2
    conn = psycopg2.connect(
        "postgresql://postgres:postgres@localhost:15432/ecm_rag",
        connect_timeout=10
    )
    cursor = conn.cursor()
    
    try:
        # Get all chunks with document metadata
        cursor.execute("""
            SELECT 
                c.id, c.text, c.sequence, c.document_id,
                d.source_path, d.source_type, d.department
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            ORDER BY c.id
        """)
        
        chunks = cursor.fetchall()
        logger.info(f"Found {len(chunks)} chunks to re-embed")
        
        if not chunks:
            logger.warning("No chunks found!")
            return
        
        # Initialize Qdrant
        qdrant = QdrantClient("http://localhost:6333", timeout=30)
        logger.info("Connected to Qdrant")
        
        # Clear existing collection
        try:
            qdrant.delete_collection("ecm_docs")
            logger.info("Deleted existing collection")
        except:
            pass
        
        # Recreate collection
        from qdrant_client.models import Distance, VectorParams
        qdrant.create_collection(
            collection_name="ecm_docs",
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        logger.info("Created fresh collection")
        
        # Initialize embedder
        embed_gen = get_embedding_generator()
        
        # Process in batches of 100
        batch_size = 100
        total_uploaded = 0
        
        for i in tqdm(range(0, len(chunks), batch_size), desc="Uploading batches"):
            batch = chunks[i:i + batch_size]
            
            # Extract texts
            texts = [chunk[1] for chunk in batch]  # chunk[1] is text
            
            # Generate embeddings
            embeddings = embed_gen.embed(texts)
            
            # Create points
            points = []
            for j, chunk in enumerate(batch):
                chunk_id, text, sequence, doc_id, source_path, source_type, department = chunk
                qdrant_id = f"{doc_id}_{sequence}"
                
                # Use numeric ID for Qdrant
                try:
                    qdrant_id_int = int(qdrant_id.replace("_", ""))
                except:
                    qdrant_id_int = hash(qdrant_id) % (10 ** 8)
                
                filename = source_path.split("\\")[-1] if source_path else "unknown"
                
                point = PointStruct(
                    id=qdrant_id_int,
                    vector=embeddings[j],
                    payload={
                        "doc_id": doc_id,
                        "filename": filename,
                        "source_type": source_type or "",
                        "department": department or "",
                        "sequence": sequence,
                        "text": text,  # FULL TEXT
                        "text_preview": text[:300],  # Preview for display
                    }
                )
                points.append(point)
            
            # Upload batch
            qdrant.upsert(collection_name="ecm_docs", points=points)
            total_uploaded += len(points)
        
        logger.info(f"✅ Successfully uploaded {total_uploaded} vectors")
        
        # Verify
        collection_info = qdrant.get_collection("ecm_docs")
        logger.info(f"Qdrant now has {collection_info.points_count} points")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    rebuild_vectors_simple()
