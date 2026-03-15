"""Cloud Layer: LLM Client.

Wrapper around HuggingFace Inference API for LLM inference.
"""

import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

HF_API_URL = "https://router.huggingface.co/featherless-ai/v1/completions"


def _env_int(name: str, default: int) -> int:
    """Read a positive integer from environment, with safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float from environment, with safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class LLMClient:
    """Client for HuggingFace Inference API.

    Supports Mistral 7B (primary) and Phi-2 (fallback).
    Includes retry logic and rate-limit handling.
    """

    def __init__(
        self,
        primary_model: str = "mistralai/Mistral-7B-Instruct-v0.3",
        fallback_model: str = "microsoft/phi-2",
        api_token: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.3,
        timeout: int = 25,
        max_retries: int = 2,
    ):
        self.primary_model = os.getenv("HF_PRIMARY_MODEL", primary_model)
        self.fallback_model = os.getenv("HF_FALLBACK_MODEL", fallback_model)
        self.api_token = api_token or os.getenv("HUGGINGFACE_API_TOKEN", "")
        self.max_tokens = _env_int("HF_MAX_TOKENS", max_tokens)
        self.temperature = _env_float("HF_TEMPERATURE", temperature)
        self.timeout = _env_int("HF_TIMEOUT_SECONDS", timeout)
        self.max_retries = _env_int("HF_MAX_RETRIES", max_retries)

        if not self.api_token:
            logger.warning(
                "No HUGGINGFACE_API_TOKEN found. Set it in .env or pass as argument."
            )

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_token}"}

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """Generate a completion from the LLM.

        Args:
            prompt: The input prompt text.
            model: Override model name. Defaults to primary_model.
            max_tokens: Override max tokens.
            temperature: Override temperature.

        Returns:
            Dict with keys: text, model, latency_ms, tokens_used.
        """
        model = model or self.primary_model
        start_time = time.time()

        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
        }

        # Try primary model with retries.
        response_text = self._call_api(model, payload)

        # Fallback to secondary model.
        if response_text is None and model == self.primary_model:
            logger.warning("Primary model failed, falling back to %s", self.fallback_model)
            response_text = self._call_api(self.fallback_model, payload)
            if response_text is not None:
                model = self.fallback_model

        elapsed_ms = round((time.time() - start_time) * 1000)

        if response_text is None:
            return {
                "text": "Error: Unable to generate response from any model.",
                "model": model,
                "latency_ms": elapsed_ms,
                "tokens_used": 0,
                "error": True,
            }

        return {
            "text": response_text.strip(),
            "model": model,
            "latency_ms": elapsed_ms,
            "tokens_used": self._estimate_tokens(response_text),
            "error": False,
        }

    def _call_api(self, model: str, payload: dict) -> Optional[str]:
        """Call the HuggingFace Inference API with retry logic.

        Args:
            model: Model name/path on HuggingFace.
            payload: Request payload.

        Returns:
            Generated text string, or None on failure.
        """
        url = HF_API_URL

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=(10, self.timeout),
                )

                if response.status_code == 200:
                    result = response.json()
                    choices = result.get("choices", []) if isinstance(result, dict) else []
                    if choices:
                        return choices[0].get("text", "")
                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get("generated_text", "")
                    return str(result)

                if response.status_code == 503:
                    wait_time = response.json().get("estimated_time", 30)
                    logger.info("Model loading, waiting %ss (attempt %s)", wait_time, attempt)
                    time.sleep(min(wait_time, 60))
                    continue

                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning("Rate limited, waiting %ss", wait_time)
                    time.sleep(wait_time)
                    continue

                logger.error("API error %s: %s", response.status_code, response.text[:200])
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

            except requests.Timeout:
                logger.warning(
                    "LLM request timeout for model %s after %ss (attempt %s/%s)",
                    model,
                    self.timeout,
                    attempt,
                    self.max_retries,
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

            except requests.RequestException as err:
                logger.error("Request failed (attempt %s): %s", attempt, err)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        return None

    def _estimate_tokens(self, text: str) -> int:
        """Rough token count estimation (4 chars ~= 1 token)."""
        return len(text) // 4
