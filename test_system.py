#!/usr/bin/env python3
"""
Quick test script for ECM RAG Chatbot
Tests the full pipeline: retrieval + LLM + citations
"""

import os
import sys
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path.cwd()))

def test_pipeline():
    """Test the complete RAG pipeline without FastAPI"""
    print("=" * 80)
    print("ECM RAG CHATBOT - QUICK TEST")
    print("=" * 80)
    
    # Test 1: Configuration
    print("\n[1] Testing Configuration...")
    try:
        from api.config import QDRANT_URL, DATABASE_URL, OPENAI_API_KEY
        print(f"   [OK] Qdrant URL: {QDRANT_URL}")
        print(f"   [OK] Database: {'Postgres' if 'postgres' in DATABASE_URL else 'SQLite'}")
        print(f"   [OK] OpenAI API Key: {'SET' if OPENAI_API_KEY else 'NOT SET'}")
    except Exception as e:
        print(f"   [ERROR] Config error: {e}")
        return False
    
    # Test 2: Database Connection
    print("\n[2] Testing Database Connection...")
    try:
        from api.db import SessionLocal, Document, Chunk
        session = SessionLocal()
        doc_count = session.query(Document).count()
        chunk_count = session.query(Chunk).count()
        session.close()
        print(f"   [OK] Connected to database")
        print(f"   [OK] Documents in DB: {doc_count}")
        print(f"   [OK] Chunks in DB: {chunk_count}")
    except Exception as e:
        print(f"   [ERROR] Database error: {e}")
        return False
    
    if doc_count == 0:
        print("\n[WARNING] No documents in database. Please ingest documents first.")
        return False
    
    # Test 3: Retriever
    print("\n[3] Testing Retriever (search for relevant documents)...")
    try:
        from api.retriever import hybrid_search
        query = "What is the timeline for ECM replacement?"
        print(f"   Query: '{query}'")
        results = hybrid_search(query, top_k=3)
        print(f"   [OK] Retrieved {len(results)} documents")
        for i, result in enumerate(results[:3], 1):
            print(f"      {i}. {result.get('filename', 'Unknown')} (score: {result.get('score', 0):.2f})")
    except Exception as e:
        print(f"   [ERROR] Retriever error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: LLM
    print("\n[4] Testing LLM Connector...")
    try:
        from api.llm import LLMConnector
        llm = LLMConnector()
        print(f"   [OK] LLM initialized: {llm.model}")
        print(f"   [OK] Temperature: {llm.temperature}")
        print(f"   [OK] Max tokens: {llm.max_tokens}")
    except Exception as e:
        print(f"   [ERROR] LLM error: {e}")
        return False
    
    # Test 5: Answer Generation
    print("\n[5] Testing Answer Generation...")
    try:
        from api.answer_generator import AnswerGenerator
        generator = AnswerGenerator()
        
        # Use real search results
        query = "What are the ECM replacement requirements?"
        answer, citations = generator.generate(query, results)
        
        print(f"   [OK] Generated answer: {len(answer)} characters")
        print(f"   [OK] Citations found: {len(citations)}")
        print(f"\n   Answer (first 200 chars):")
        print(f"   {answer[:200]}...")
        print(f"\n   Citations:")
        for cite in citations[:3]:
            print(f"      - {cite['filename']} ({cite['citation_count']} references)")
    except Exception as e:
        print(f"   [ERROR] Answer generation error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 6: Full Query
    print("\n[6] Testing Full Pipeline (Query -> Retrieve -> Generate -> Citations)...")
    try:
        # Use retriever + answer gen + LLM
        query = "What is the status of the ECM project?"
        print(f"   Query: '{query}'")
        
        # Retrieve
        from api.retriever import hybrid_search
        search_results = hybrid_search(query, top_k=5)
        
        # Generate answer
        from api.answer_generator import AnswerGenerator
        generator = AnswerGenerator()
        answer, citations = generator.generate(query, search_results)
        
        print(f"   [OK] Retrieved: {len(search_results)} documents")
        print(f"   [OK] Answer length: {len(answer)} chars")
        print(f"   [OK] Citations: {len(citations)}")
        print(f"\n   Full Response:")
        print(f"   Q: {query}")
        print(f"   A: {answer[:250]}...")
        print(f"\n   Sources cited:")
        for i, cite in enumerate(citations[:3], 1):
            print(f"      {i}. {cite['filename']}")
        
    except Exception as e:
        print(f"   [ERROR] Full pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("[SUCCESS] ALL TESTS PASSED - System is ready to use!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Start backend:  python -m uvicorn api.main:app --reload")
    print("  2. Start frontend: cd ui && npm run dev")
    print("  3. Open browser:   http://localhost:3000")
    return True

if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    success = test_pipeline()
    sys.exit(0 if success else 1)
