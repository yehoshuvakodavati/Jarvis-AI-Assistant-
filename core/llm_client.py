"""
Unified LLM Client for Jarvis Multi-Agent AI Operating System.

Handles all communication with Ollama including:
- Text generation with retry, timeout, and model selection
- Embedding generation via /api/embeddings
- Structured JSON output
- Health checking and model availability
- Exponential backoff for transient failures
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from config import (
    OLLAMA_GENERATE_URL,
    OLLAMA_EMBED_URL,
    OLLAMA_TAGS_URL,
    OLLAMA_TIMEOUT,
    OLLAMA_MAX_RETRIES,
    OLLAMA_RETRY_DELAY,
    MODEL_EMBEDDING,
    TEMP_STRUCTURED,
    TEMP_CONVERSATIONAL,
    TEMP_CREATIVE,
    TEMP_CODE,
)
from core.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
    LLMResponseError,
    LLMModelNotFoundError,
    LLMRateLimitError,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Production-grade LLM client with resilience patterns.

    Usage:
        client = LLMClient()
        response = client.generate("Explain quantum computing", model="llama3")
        embedding = client.embed("Some text to embed")
    """

    _instance: Optional[LLMClient] = None
    _initialized: bool = False

    def __new__(cls) -> LLMClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if LLMClient._initialized:
            return
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._available_models: set[str] = set()
        self._refresh_models()
        LLMClient._initialized = True

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        json_mode: bool = False,
        timeout: int | None = None,
    ) -> str:
        """
        Generate text from an LLM with full resilience.

        Args:
            prompt: The user prompt.
            model: Model name (e.g., 'llama3'). Auto-detected if None.
            system: Optional system prompt.
            temperature: Sampling temperature. Auto-selected if None.
            max_tokens: Maximum tokens to generate.
            json_mode: If True, requests structured JSON output.
            timeout: Override default timeout.

        Returns:
            Generated text string.

        Raises:
            LLMConnectionError: Cannot reach Ollama.
            LLMTimeoutError: Request timed out.
            LLMResponseError: Invalid response structure.
        """
        resolved_model = model or self._infer_model(prompt, json_mode)
        resolved_temp = temperature if temperature is not None else self._infer_temperature(prompt, json_mode)
        resolved_timeout = timeout or OLLAMA_TIMEOUT

        payload: Dict[str, Any] = {
            "model": resolved_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": resolved_temp,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            # Best-effort JSON mode hint
            payload["format"] = "json"

        return self._request_with_retry(
            OLLAMA_GENERATE_URL,
            payload,
            timeout=resolved_timeout,
            response_extractor=self._extract_generate_response,
        )

    def generate_structured(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = TEMP_STRUCTURED,
        max_tokens: int = 4096,
        timeout: int | None = None,
        parser: Callable[[str], Any] | None = None,
    ) -> Any:
        """
        Generate structured output and parse it.

        Args:
            prompt: The user prompt.
            model, system, temperature, max_tokens, timeout: Passed to generate().
            parser: Optional callable to parse the response string.
                    Defaults to JSON parsing.

        Returns:
            Parsed structured data (dict, list, or custom type).
        """
        raw = self.generate(
            prompt,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            timeout=timeout,
        )
        if parser:
            return parser(raw)
        return self._safe_json_parse(raw)

    def embed(
        self,
        text: str,
        *,
        model: str = MODEL_EMBEDDING,
        timeout: int | None = None,
    ) -> List[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Text to embed.
            model: Embedding model name.
            timeout: Override default timeout.

        Returns:
            List of float values (embedding vector).

        Raises:
            LLMConnectionError, LLMTimeoutError, LLMResponseError
        """
        payload = {"model": model, "prompt": text}
        resolved_timeout = timeout or OLLAMA_TIMEOUT

        return self._request_with_retry(
            OLLAMA_EMBED_URL,
            payload,
            timeout=resolved_timeout,
            response_extractor=self._extract_embed_response,
        )

    def embed_batch(
        self,
        texts: List[str],
        *,
        model: str = MODEL_EMBEDDING,
        timeout: int | None = None,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts sequentially.
        (Ollama does not natively support batch embeddings.)
        """
        results: List[List[float]] = []
        for text in texts:
            try:
                results.append(self.embed(text, model=model, timeout=timeout))
            except Exception as e:
                logger.warning(f"Embedding failed for text chunk: {e}")
                results.append([])
        return results

    def check_health(self) -> bool:
        """Check if Ollama is reachable and has at least one model."""
        try:
            resp = self.session.get(OLLAMA_TAGS_URL, timeout=5)
            resp.raise_for_status()
            self._refresh_models()
            return len(self._available_models) > 0
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False

    def is_model_available(self, model: str) -> bool:
        """Check if a specific model is available."""
        if not self._available_models:
            self._refresh_models()
        return model in self._available_models

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------

    def _request_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        *,
        timeout: int,
        response_extractor: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        """Execute an HTTP request with exponential backoff retry."""
        last_exception: Exception | None = None
        delay = OLLAMA_RETRY_DELAY

        for attempt in range(1, OLLAMA_MAX_RETRIES + 1):
            try:
                logger.debug(f"LLM request attempt {attempt}/{OLLAMA_MAX_RETRIES} to {url}")
                resp = self.session.post(url, json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                return response_extractor(data)

            except requests.exceptions.ConnectionError as e:
                last_exception = LLMConnectionError(details={"url": url, "attempt": attempt})
                logger.warning(f"LLM connection error (attempt {attempt}): {e}")
            except requests.exceptions.Timeout as e:
                last_exception = LLMTimeoutError(details={"url": url, "timeout": timeout, "attempt": attempt})
                logger.warning(f"LLM timeout (attempt {attempt}): {e}")
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 0
                if status == 429:
                    last_exception = LLMRateLimitError(details={"attempt": attempt})
                elif status == 404:
                    model = payload.get("model", "unknown")
                    raise LLMModelNotFoundError(model)
                else:
                    last_exception = LLMResponseError(
                        f"HTTP {status}", details={"attempt": attempt}
                    )
                logger.warning(f"LLM HTTP error (attempt {attempt}): {e}")
            except Exception as e:
                last_exception = LLMResponseError(str(e), details={"attempt": attempt})
                logger.warning(f"LLM unexpected error (attempt {attempt}): {e}")

            if attempt < OLLAMA_MAX_RETRIES:
                logger.info(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff

        raise last_exception or LLMResponseError("All retry attempts exhausted")

    @staticmethod
    def _extract_generate_response(data: Dict[str, Any]) -> str:
        """Extract text from Ollama generate response."""
        response = data.get("response", "")
        if not isinstance(response, str):
            raise LLMResponseError(f"Unexpected response type: {type(response)}")
        return response.strip()

    @staticmethod
    def _extract_embed_response(data: Dict[str, Any]) -> List[float]:
        """Extract embedding vector from Ollama embed response."""
        embedding = data.get("embedding", [])
        if not isinstance(embedding, list):
            raise LLMResponseError(f"Unexpected embedding type: {type(embedding)}")
        return embedding

    def _refresh_models(self) -> None:
        """Refresh the cache of available models from Ollama."""
        try:
            resp = self.session.get(OLLAMA_TAGS_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            self._available_models = {m.get("name", "").split(":")[0] for m in models if m.get("name")}
            logger.debug(f"Available models: {self._available_models}")
        except Exception as e:
            logger.warning(f"Could not refresh model list: {e}")
            self._available_models = set()

    @staticmethod
    def _infer_model(prompt: str, json_mode: bool) -> str:
        """Infer the best model for a given prompt."""
        p = prompt.lower()
        from config import MODEL_COMMANDER, MODEL_CODER, MODEL_CONVERSATIONAL

        if json_mode:
            return MODEL_COMMANDER
        if any(kw in p for kw in ("code", "python", "java", "javascript", "function", "class", "algorithm")):
            return MODEL_CODER
        if any(kw in p for kw in ("plan", "schedule", "roadmap", "strategy")):
            return MODEL_COMMANDER
        return MODEL_CONVERSATIONAL

    @staticmethod
    def _infer_temperature(prompt: str, json_mode: bool) -> float:
        """Infer appropriate temperature for a prompt."""
        if json_mode:
            return TEMP_STRUCTURED
        p = prompt.lower()
        if any(kw in p for kw in ("plan", "schedule", "roadmap", "brainstorm", "creative")):
            return TEMP_CREATIVE
        if any(kw in p for kw in ("code", "python", "java", "function")):
            return TEMP_CODE
        return TEMP_CONVERSATIONAL

    @staticmethod
    def _safe_json_parse(text: str) -> Any:
        """Safely parse JSON, extracting from code blocks if needed."""
        text = text.strip()
        # Try to extract JSON from markdown code blocks
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove opening fence
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Raw text: {text[:200]}")
            # Return as-is if not valid JSON
            return {"raw_response": text}
