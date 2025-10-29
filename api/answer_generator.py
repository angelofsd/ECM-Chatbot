"""
RAG answer generator for ECM chatbot.

Takes retrieved documents, generates context-aware answers,
and provides citations back to source documents.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Generator

from api.llm import LLMConnector, LLMConfig
from api.retriever import SearchResult

logger = logging.getLogger(__name__)

# System prompt for the RAG assistant
SYSTEM_PROMPT = """You are a helpful assistant for New Mexico Mutual's ECM (Enterprise Content Management) replacement project.

You have access to internal documents including RFPs, vendor responses, research notes, meeting minutes, and emails.

When answering questions:
1. Use the provided context documents to inform your answer
2. Be accurate and cite specific document titles when referencing information
3. If information is not in the documents, say so clearly
4. For complex topics, organize your answer with bullet points or sections
5. Maintain a professional, concise tone
6. If asked about vendor comparisons, provide balanced information from the documents

When you cite a document, use the format: [filename or source title]

Format your response clearly and be helpful to project stakeholders."""


class CitationTracker:
    """Track which documents were used in the answer."""
    
    def __init__(self):
        self.citations: Dict[str, int] = {}  # filename -> count of references
        self.docs_used: List[str] = []  # filenames in order of use
    
    def add_citation(self, filename: str) -> None:
        """Record a citation to a document."""
        self.citations[filename] = self.citations.get(filename, 0) + 1
        if filename not in self.docs_used:
            self.docs_used.append(filename)
    
    def get_cited_docs(self) -> List[Dict[str, Any]]:
        """Get list of cited documents with metadata."""
        return [
            {
                "filename": filename,
                "citation_count": self.citations[filename],
                "order": i,
            }
            for i, filename in enumerate(self.docs_used)
        ]


class AnswerGenerator:
    """Generate answers from retrieved documents using LLM."""
    
    def __init__(
        self,
        llm_connector: Optional[LLMConnector] = None,
        max_context_tokens: int = 3000,
    ):
        """
        Initialize answer generator.
        
        Args:
            llm_connector: LLMConnector instance (creates new if None)
            max_context_tokens: Max tokens to include in context (rest of prompt budget)
        """
        self.llm = llm_connector or LLMConnector()
        self.max_context_tokens = max_context_tokens
    
    def _format_context(self, results: List[SearchResult]) -> Tuple[str, CitationTracker]:
        """
        Format retrieved documents into context string.
        
        Args:
            results: List of SearchResult objects from retriever
            
        Returns:
            Tuple of (formatted_context_str, citation_tracker)
        """
        citations = CitationTracker()
        context_parts = []
        
        total_tokens = 0
        for result in results:
            # Get filename from source_path
            filename = result.get("filename", "Unknown")
            
            # Track citation
            citations.add_citation(filename)
            
            # Count tokens in this chunk
            chunk_tokens = self.llm.count_tokens(result.get("text", ""))
            if total_tokens + chunk_tokens > self.max_context_tokens:
                logger.info(f"Context token limit reached ({total_tokens}/{self.max_context_tokens})")
                break
            
            total_tokens += chunk_tokens
            
            # Format chunk with source attribution
            context_parts.append(
                f"[{filename} - Relevance: {result.get('similarity_score', 0):.2%}]\n"
                f"{result.get('text', '')}\n"
            )
        
        context_str = "\n---\n".join(context_parts)
        
        logger.info(f"Context: {len(context_parts)} chunks, {total_tokens} tokens")
        
        return context_str, citations
    
    def generate(
        self,
        query: str,
        search_results: List[SearchResult],
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate an answer from retrieved documents.
        
        Args:
            query: User's question
            search_results: List of SearchResult dicts from retriever
            verbose: Log token usage and timing
            
        Returns:
            Dict with keys:
                - "answer": Generated answer (str)
                - "citations": List of cited documents
                - "tokens_used": Approximate tokens (prompt + response)
                - "sources_count": Number of documents used
                - "model": Model used
        """
        if not search_results:
            return {
                "answer": "I'm sorry, I couldn't find any relevant documents to answer your question. Please try a different query or provide more context.",
                "citations": [],
                "tokens_used": 0,
                "sources_count": 0,
                "model": self.llm.config.model,
            }
        
        # Format context from search results
        context_str, citations = self._format_context(search_results)
        
        # Build message list
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"""Please answer the following question using the provided document excerpts.

QUESTION: {query}

CONTEXT (document excerpts):
{context_str}

Provide a clear, helpful answer citing the relevant documents.""",
            },
        ]
        
        # Get completion
        result = self.llm.complete(messages, verbose=verbose)
        
        # Extract answer
        answer = result.get("response", "")
        
        return {
            "answer": answer,
            "citations": citations.get_cited_docs(),
            "tokens_used": (result.get("tokens_prompt", 0) or 0) + result.get("tokens_response", 0),
            "sources_count": len(search_results),
            "model": self.llm.config.model,
            "finish_reason": result.get("finish_reason"),
        }
    
    def generate_streaming(
        self,
        query: str,
        search_results: List[SearchResult],
        verbose: bool = False,
    ) -> Generator[Tuple[str, List[Dict[str, Any]]], None, None]:
        """
        Generate an answer using streaming (for real-time UI updates).
        
        Args:
            query: User's question
            search_results: List of SearchResult dicts
            verbose: Log token usage
            
        Yields:
            Tuples of (chunk, citations) as they stream in
        """
        if not search_results:
            yield "I'm sorry, I couldn't find any relevant documents to answer your question."
            return [], []
        
        # Format context
        context_str, citations = self._format_context(search_results)
        
        # Build messages
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"""Please answer the following question using the provided document excerpts.

QUESTION: {query}

CONTEXT (document excerpts):
{context_str}

Provide a clear, helpful answer citing the relevant documents.""",
            },
        ]
        
        # Stream completion
        for chunk in self.llm.stream(messages, verbose=verbose):
            yield chunk, citations.get_cited_docs()


def get_answer_generator(
    llm_connector: Optional[LLMConnector] = None,
    max_context_tokens: int = 3000,
) -> AnswerGenerator:
    """
    Factory function to get an answer generator.
    
    Args:
        llm_connector: Optional LLMConnector instance
        max_context_tokens: Max tokens for context documents
        
    Returns:
        AnswerGenerator instance
    """
    return AnswerGenerator(llm_connector, max_context_tokens)
