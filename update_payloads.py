#!/usr/bin/env python3
"""
Update existing Qdrant payloads to include full text (without re-embedding).
"""
import psycopg2
import requests
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_payloads():
    """Update Qdrant payloads with full text from Postgres."""
    
    # Connect to Postgres
    conn = psycopg2.connect(
        "postgresql://postgres:postgres@localhost:15432/ecm_rag",
        connect_timeout=10
    )
    cursor = conn.cursor()
    
    try:
        # Get all chunks
        cursor.execute("""
            SELECT c.id, c.text, c.sequence, c.document_id
            FROM chunks c
            ORDER BY c.id
        """)
        
        chunks = cursor.fetchall()
        logger.info(f"Found {len(chunks)} chunks to update")
        
        success_count = 0
        error_count = 0
        
        for chunk in tqdm(chunks, desc="Updating payloads"):
            chunk_id, text, sequence, doc_id = chunk
            
            # Calculate Qdrant ID (same as ingestion)
            qdrant_id = f"{doc_id}_{sequence}"
            try:
                qdrant_id_int = int(qdrant_id.replace("_", ""))
            except:
                qdrant_id_int = hash(qdrant_id) % (10 ** 8)
            
            # Update payload via Qdrant API
            try:
                response = requests.post(
                    f"http://localhost:6333/collections/ecm_docs/points/payload",
                    json={
                        "points": [qdrant_id_int],
                        "payload": {
                            "text": text,
                            "text_preview": text[:300]
                        }
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    logger.warning(f"Failed to update {qdrant_id_int}: {response.status_code}")
                    error_count += 1
                    
            except Exception as e:
                logger.warning(f"Error updating {qdrant_id_int}: {e}")
                error_count += 1
        
        logger.info(f"✅ Updated {success_count} payloads ({error_count} errors)")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_payloads()
