"""
OpenAI LLM connector for ECM RAG chatbot.

Provides a thin wrapper around OpenAI's chat completion API with:
- Configurable model selection (GPT-4, GPT-4o, etc.)
- Token counting for prompt/response sizing
- Error handling with retry logic
- Cost tracking (optional)
"""

import os
import logging
from typing import Optional, List, Dict, Any

from openai import OpenAI, RateLimitError, APIError
import tiktoken

logger = logging.getLogger(__name__)


class LLMConfig:
    """Configuration for LLM connector."""
    
    def __init__(
        self,
        model: str = "gpt-5-mini",  # Default to GPT-5 mini (faster/cost-effective)
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        api_key: Optional[str] = None,
    ):
        """
        Initialize LLM configuration.
        
        Args:
            model: OpenAI model name (gpt-4, gpt-4o, gpt-4o-mini, etc.)
            temperature: Sampling temperature (0.0-2.0). Lower = more deterministic.
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY must be set in environment or passed to LLMConfig")
    
    def to_dict(self) -> Dict[str, Any]:
        """Return config as dictionary (excluding API key for safety)."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }


class LLMConnector:
    """OpenAI chat completion connector with token counting."""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize LLM connector.
        
        Args:
            config: LLMConfig instance. If None, uses defaults from environment.
        """
        self.config = config or LLMConfig()
        self.client = OpenAI(api_key=self.config.api_key)
        
        # Load tokenizer for the model
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.config.model)
        except KeyError:
            # Fallback if model not found in tiktoken
            logger.warning(f"Model {self.config.model} not found in tiktoken, using cl100k_base")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        logger.info(f"Initialized LLMConnector: model={self.config.model}")
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using the model's tokenizer.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))
    
    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Count tokens in a message list (approximation).
        
        Uses rough formula: approximately 4 tokens per message + token count of content.
        For accurate counts, OpenAI recommends this approach.
        
        Args:
            messages: List of message dicts with "role" and "content"
            
        Returns:
            Approximate token count
        """
        total = 0
        for msg in messages:
            # Each message has overhead
            total += 4
            # Plus content tokens
            total += self.count_tokens(msg.get("content", ""))
        return total
    
    def complete(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Get completion from OpenAI chat API.
        
        Args:
            messages: List of message dicts with "role" and "content"
            max_retries: Max retries on rate limit errors
            verbose: Log token counts and timing info
            
        Returns:
            Dict with keys:
                - "response": The assistant's message content (str)
                - "tokens_prompt": Tokens in prompt
                - "tokens_response": Tokens in response
                - "model": Model used
                - "finish_reason": "stop", "length", etc.
        
        Raises:
            APIError: If request fails after retries
        """
        if verbose:
            prompt_tokens = self.count_messages_tokens(messages)
            logger.info(f"Prompt: {prompt_tokens} tokens, max_response: {self.config.max_tokens}")
        
        # Retry logic for rate limits
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    top_p=self.config.top_p,
                )
                
                assistant_message = response.choices[0].message.content
                response_tokens = self.count_tokens(assistant_message)
                
                if verbose:
                    logger.info(f"Response: {response_tokens} tokens, finish_reason={response.choices[0].finish_reason}")
                
                return {
                    "response": assistant_message,
                    "tokens_prompt": prompt_tokens if verbose else None,
                    "tokens_response": response_tokens,
                    "model": self.config.model,
                    "finish_reason": response.choices[0].finish_reason,
                }
            
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"Rate limit after {max_retries} retries: {e}")
                    raise
            
            except APIError as e:
                logger.error(f"API error: {e}")
                raise
        
        raise RuntimeError("Completion failed after retries")
    
    def stream(
        self,
        messages: List[Dict[str, str]],
        verbose: bool = False,
    ):
        """
        Stream completion tokens from OpenAI (generator).
        
        Args:
            messages: List of message dicts with "role" and "content"
            verbose: Log token counts
            
        Yields:
            Text chunks as they arrive from the API
        """
        if verbose:
            prompt_tokens = self.count_messages_tokens(messages)
            logger.info(f"Streaming: Prompt {prompt_tokens} tokens")
        
        with self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
            stream=True,
        ) as stream:
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content


def get_llm_connector(model: Optional[str] = None) -> LLMConnector:
    """
    Factory function to get a singleton LLM connector.
    
    Args:
        model: Override default model (from env or config)
        
    Returns:
        LLMConnector instance
    """
    config_model = model or os.getenv("LLM_MODEL", "gpt-5-mini")
    config = LLMConfig(model=config_model)
    return LLMConnector(config)
