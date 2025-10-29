#!/usr/bin/env python3
"""
Test script for LLM connector and answer generator.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.llm import LLMConnector, LLMConfig
from api.answer_generator import AnswerGenerator


def test_llm_connector():
    """Test basic LLM connector functionality."""
    print("[TEST] LLM Connector\n")
    
    # Load .env
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    try:
        # Create connector
        config = LLMConfig(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=256,
        )
        llm = LLMConnector(config)
        print(f"✓ LLMConnector initialized: {config.model}")
        
        # Test token counting
        text = "This is a test sentence for token counting."
        tokens = llm.count_tokens(text)
        print(f"✓ Token counting works: '{text}' = {tokens} tokens")
        
        # Test simple completion
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "What is 2+2?",
            },
        ]
        
        result = llm.complete(messages, verbose=True)
        print(f"✓ Completion successful:")
        print(f"  Response: {result['response'][:100]}...")
        print(f"  Tokens: {result['tokens_response']}")
        print(f"  Finish reason: {result['finish_reason']}")
        
        return True
    
    except Exception as e:
        print(f"✗ LLM Connector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_answer_generator():
    """Test answer generator with mock retrieval results."""
    print("\n[TEST] Answer Generator\n")
    
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    try:
        # Create mock search results
        mock_results = [
            {
                "filename": "RFP_Example.pdf",
                "text": "The ECM system must support workflow automation, document classification, and integration with existing systems. Vendors should provide implementation support and training.",
                "similarity_score": 0.92,
                "source_type": "pdf",
            },
            {
                "filename": "Vendor_Comparison.msg",
                "text": "Laserfiche provides strong workflow capabilities with competitive pricing. Box offers cloud-first architecture. OpenText has enterprise-level features.",
                "similarity_score": 0.87,
                "source_type": "email",
            },
        ]
        
        # Create answer generator
        gen = AnswerGenerator(max_context_tokens=2000)
        print("✓ AnswerGenerator initialized")
        
        # Generate answer
        query = "What are the key requirements for the ECM system?"
        result = gen.generate(
            query=query,
            search_results=mock_results,
            verbose=True,
        )
        
        print(f"✓ Answer generation successful:")
        print(f"  Query: {query}")
        print(f"  Answer: {result['answer'][:200]}...")
        print(f"  Sources: {result['sources_count']}")
        print(f"  Citations: {[c['filename'] for c in result['citations']]}")
        print(f"  Tokens used: {result['tokens_used']}")
        
        return True
    
    except Exception as e:
        print(f"✗ Answer Generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2b: LLM Connector & Answer Generator Tests")
    print("=" * 60)
    print()
    
    test1_ok = test_llm_connector()
    test2_ok = test_answer_generator()
    
    print("\n" + "=" * 60)
    if test1_ok and test2_ok:
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        print("=" * 60)
        sys.exit(1)
