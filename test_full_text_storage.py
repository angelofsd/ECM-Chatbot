#!/usr/bin/env python3
"""
Test script to verify full text is stored in Qdrant, not just 200-char preview.

This test verifies the fix for storing complete chunk text in Qdrant's payload.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(override=True)

from qdrant_client import QdrantClient
from api.config import QDRANT_URL, QDRANT_COLLECTION


def test_full_text_in_qdrant():
    """Verify that Qdrant stores full text, not just 200-char preview."""
    print("\n[TEST] Checking if Qdrant stores full text\n")

    try:
        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL)

        # Get collection info
        try:
            collection_info = client.get_collection(QDRANT_COLLECTION)
            print(f"✓ Connected to Qdrant collection: {QDRANT_COLLECTION}")
            print(f"  Total vectors: {collection_info.points_count}")
        except Exception as e:
            print(f"✗ Collection '{QDRANT_COLLECTION}' not found: {e}")
            print(
                "  Run ingestion first: python ingest_pool.py --workers 4 --max-pdfs 5"
            )
            return False

        if collection_info.points_count == 0:
            print(f"⚠ Collection is empty. Run ingestion first.")
            return False

        # Scroll through a few points to check payload structure
        scroll_result = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=10,
            with_payload=True,
        )

        points = scroll_result[0]
        if not points:
            print("✗ No points retrieved from Qdrant")
            return False

        print(f"\n✓ Retrieved {len(points)} sample points")

        # Check each point's payload for full text
        issues_found = []
        full_text_found = 0

        for i, point in enumerate(points):
            payload = point.payload

            # Check if 'text' field exists
            if "text" not in payload:
                issues_found.append(f"Point {i}: Missing 'text' field in payload")
                continue

            text = payload["text"]
            text_len = len(text)

            # Check if text is suspiciously short (likely a preview)
            if text_len <= 200:
                print(
                    f"  Point {i}: Text is only {text_len} chars (might be short chunk or preview)"
                )
            else:
                full_text_found += 1
                print(f"  Point {i}: ✓ Full text stored ({text_len} chars)")

            # Also check for old 'text_preview' field (should not exist)
            if "text_preview" in payload:
                issues_found.append(
                    f"Point {i}: Old 'text_preview' field still exists!"
                )

        # Report results
        print(f"\nResults:")
        print(f"  Points checked: {len(points)}")
        print(f"  Points with full text (>200 chars): {full_text_found}")
        print(f"  Issues found: {len(issues_found)}")

        if issues_found:
            print("\nIssues:")
            for issue in issues_found:
                print(f"  ✗ {issue}")
            return False

        # Check for 'text_preview' field in any point (old format)
        has_old_format = any("text_preview" in p.payload for p in points)
        if has_old_format:
            print("\n✗ FAIL: Some points still use old 'text_preview' field")
            print("  Run rebuild_vectors.py to update existing vectors:")
            print("  USE_SQLITE=false python rebuild_vectors.py")
            return False

        print("\n✓ SUCCESS: All points store full text in 'text' field")
        print("  (Some chunks may be naturally short, which is OK)")

        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_payload_structure():
    """Verify the payload structure is correct."""
    print("\n[TEST] Checking payload structure\n")

    try:
        client = QdrantClient(url=QDRANT_URL)

        # Get a single point
        scroll_result = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=1,
            with_payload=True,
        )

        points = scroll_result[0]
        if not points:
            print("✗ No points in collection")
            return False

        point = points[0]
        payload = point.payload

        print("Sample payload structure:")
        for key, value in payload.items():
            if key == "text":
                print(f"  {key}: <{len(value)} chars>")
            else:
                print(f"  {key}: {value}")

        # Check required fields
        required_fields = [
            "doc_id",
            "filename",
            "source_type",
            "department",
            "sequence",
            "text",
        ]
        missing_fields = [f for f in required_fields if f not in payload]

        if missing_fields:
            print(f"\n✗ Missing required fields: {missing_fields}")
            return False

        print("\n✓ Payload structure is correct")
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Full Text Storage Test for Qdrant")
    print("=" * 60)

    test1_ok = test_payload_structure()
    test2_ok = test_full_text_in_qdrant()

    print("\n" + "=" * 60)
    if test1_ok and test2_ok:
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ Some tests failed or collection is empty")
        print("  To fix: Run 'USE_SQLITE=false python rebuild_vectors.py'")
        print("=" * 60)
        sys.exit(1)
