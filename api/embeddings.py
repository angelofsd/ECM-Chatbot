"""
Embedding utilities that support both local models and OpenAI API.

This module provides a unified interface for generating embeddings,
automatically switching between sentence-transformers (local) and 
OpenAI's embedding API based on configuration.
"""

import logging
from typing import List, Union
import numpy as np

from api.config import (
    USE_OPENAI_EMBEDDINGS,
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    LOG_LEVEL,
)

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)


class EmbeddingGenerator:
    """
    Unified embedding generator supporting both local and API-based models.
    
    Usage:
        embedder = EmbeddingGenerator()
        embeddings = embedder.embed(["text1", "text2"])
    """
    
    def __init__(self):
        """Initialize the appropriate embedding backend."""
        self.use_openai = USE_OPENAI_EMBEDDINGS
        self.model_name = EMBEDDING_MODEL
        self.dimension = EMBEDDING_DIMENSION
        
        if self.use_openai:
            self._init_openai()
        else:
            self._init_local()
    
    def _init_openai(self):
        """Initialize OpenAI client."""
        if not OPENAI_API_KEY:
            raise ValueError(
                "USE_OPENAI_EMBEDDINGS=true but OPENAI_API_KEY is not set. "
                "Please set OPENAI_API_KEY environment variable."
            )
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info(f"Using OpenAI embeddings: {self.model_name} ({self.dimension}d)")
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )
    
    def _init_local(self):
        """Initialize local sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded successfully ({self.dimension}d)")
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )
    
    def embed(self, texts: Union[str, List[str]], batch_size: int = 100) -> np.ndarray:
        """
        Generate embeddings for one or more texts.
        
        Args:
            texts: Single text or list of texts to embed
            batch_size: Batch size for processing (applies to both local and OpenAI)
        
        Returns:
            numpy array of shape (n_texts, embedding_dimension)
        """
        # Normalize input to list
        if isinstance(texts, str):
            texts = [texts]
            single_input = True
        else:
            single_input = False
        
        if not texts:
            return np.array([])
        
        # Generate embeddings
        if self.use_openai:
            embeddings = self._embed_openai(texts, batch_size)
        else:
            embeddings = self._embed_local(texts, batch_size)
        
        # Return single vector if single input
        if single_input:
            return embeddings[0]
        
        return embeddings
    
    def _embed_openai(self, texts: List[str], batch_size: int) -> np.ndarray:
        """Generate embeddings using OpenAI API."""
        all_embeddings = []
        
        # Process in batches to respect API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model_name
                )
                
                # Extract embeddings from response
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"OpenAI API error for batch {i//batch_size}: {e}")
                raise
        
        return np.array(all_embeddings)
    
    def _embed_local(self, texts: List[str], batch_size: int) -> np.ndarray:
        """Generate embeddings using local model."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 10,
            convert_to_numpy=True
        )
        return embeddings


# Global singleton instance
_embedding_generator = None


def get_embedding_generator() -> EmbeddingGenerator:
    """
    Get or create the global embedding generator instance.
    
    Returns:
        EmbeddingGenerator: Singleton instance
    """
    global _embedding_generator
    
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    
    return _embedding_generator


def embed_texts(texts: Union[str, List[str]], batch_size: int = 100) -> np.ndarray:
    """
    Convenience function to embed texts using the global generator.
    
    Args:
        texts: Single text or list of texts
        batch_size: Batch size for processing
    
    Returns:
        numpy array of embeddings
    """
    generator = get_embedding_generator()
    return generator.embed(texts, batch_size)


if __name__ == "__main__":
    # Test the embedding generator
    import sys
    
    print("=== Testing Embedding Generator ===")
    print(f"Mode: {'OpenAI' if USE_OPENAI_EMBEDDINGS else 'Local'}")
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Dimension: {EMBEDDING_DIMENSION}")
    print()
    
    try:
        embedder = get_embedding_generator()
        
        # Test single text
        test_text = "This is a test document about ECM replacement procedures."
        print(f"Test text: {test_text}")
        
        embedding = embed_texts(test_text)
        print(f"Embedding shape: {embedding.shape}")
        print(f"First 5 values: {embedding[:5]}")
        print()
        
        # Test batch
        test_batch = [
            "Document about claims processing",
            "Email regarding policy updates",
            "Technical specification for system migration"
        ]
        print(f"Test batch: {len(test_batch)} texts")
        
        embeddings = embed_texts(test_batch)
        print(f"Embeddings shape: {embeddings.shape}")
        print(f"Success! ✓")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
