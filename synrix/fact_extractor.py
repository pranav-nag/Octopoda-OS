"""
Octopoda Fact Extractor — Multi-Provider LLM Fact Decomposition
================================================================
Decomposes raw memory text into clean, self-contained facts before
embedding. Dramatically improves semantic search quality (50% → 88%+).

Supports multiple LLM providers:
    - platform : Free tier using Octopoda's shared API key (100 extractions/user)
    - ollama   : Local LLM via Ollama (free, self-hosted)
    - openai   : OpenAI API (GPT-4o-mini, best quality)
    - anthropic: Anthropic API (Claude)
    - none     : Skip fact extraction (embedding-only mode)

Falls back gracefully: openai/anthropic → ollama → raw text.

Configuration via env vars:
    OCTOPODA_LLM_PROVIDER   (default: platform) — platform | ollama | openai | anthropic | none
    OCTOPODA_PLATFORM_OPENAI_KEY (required for platform provider — Octopoda's shared key)
    OCTOPODA_OLLAMA_URL     (default: http://localhost:11434)
    OCTOPODA_OLLAMA_MODEL   (default: llama3.2)
    OCTOPODA_OPENAI_API_KEY (required for openai provider)
    OCTOPODA_OPENAI_MODEL   (default: gpt-4o-mini)
    OCTOPODA_OPENAI_BASE_URL (default: https://api.openai.com/v1)
        — Change this to use ANY OpenAI-compatible API:
          Groq:     https://api.groq.com/openai/v1
          Together: https://api.together.xyz/v1
          Mistral:  https://api.mistral.ai/v1
          Local:    http://localhost:11434/v1
    OCTOPODA_ANTHROPIC_API_KEY (required for anthropic provider)
    OCTOPODA_ANTHROPIC_MODEL   (default: claude-haiku-4-5-20251001)
    OCTOPODA_LLM_MAX_CONCURRENT (default: 2) — max parallel LLM calls
    OCTOPODA_LLM_TIMEOUT    (default: 60) — seconds before timeout
"""

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import List, Optional


EXTRACTION_PROMPT = '''Extract individual facts from this text. Each fact must be a short, self-contained statement with the topic category in parentheses.

Text: "{text}"

Rules:
- Each fact is one clear statement
- Include category tags in parentheses at the end
- Use third person ("User" not "I")
- Return ONLY a JSON array of strings

Example: ["User is vegetarian (food preference, diet)", "User lives in London (location, city)"]

JSON array:'''


@dataclass
class FactExtractionResult:
    """Result of fact extraction from text."""
    facts: List[str]
    source_text: str
    extraction_time_ms: float
    used_llm: bool
    provider: str = "none"

    @property
    def used_ollama(self) -> bool:
        """Backward compatibility alias."""
        return self.used_llm


class FactExtractor:
    """Extracts structured facts from text using configurable LLM providers."""

    _instance: Optional["FactExtractor"] = None
    _lock = threading.Lock()
    _semaphore: Optional[threading.Semaphore] = None

    def __init__(self):
        self._provider: str = "none"
        self._ollama_url: str = ""
        self._model_name: str = ""
        self._available: bool = False
        self._timeout: int = 60
        # API provider config
        self._openai_key: str = ""
        self._openai_model: str = ""
        self._openai_base_url: str = "https://api.openai.com/v1"
        self._anthropic_key: str = ""
        self._anthropic_model: str = ""

    @classmethod
    def get(cls, config: dict = None) -> Optional["FactExtractor"]:
        """Get the fact extractor, or None if no LLM is available.

        Args:
            config: Optional per-tenant config dict with keys like
                    llm_provider, openai_api_key, anthropic_api_key, etc.
                    If None, falls back to env vars (backward compatible).
        """
        # If per-tenant config is provided, create a fresh instance (not singleton)
        if config and config.get("llm_provider"):
            return cls._from_config(config)

        # Default singleton behavior (env vars)
        if cls._instance is not None:
            return cls._instance if cls._instance._available else None

        provider = os.environ.get("OCTOPODA_LLM_PROVIDER", "ollama").lower().strip()
        max_concurrent = int(os.environ.get("OCTOPODA_LLM_MAX_CONCURRENT", "2"))
        timeout = int(os.environ.get("OCTOPODA_LLM_TIMEOUT", "60"))

        # Init semaphore once
        if cls._semaphore is None:
            cls._semaphore = threading.Semaphore(max_concurrent)

        if provider == "none":
            cls._instance = cls()
            return None

        if provider == "platform":
            return cls._init_platform(timeout)
        elif provider == "openai":
            return cls._init_openai(timeout)
        elif provider == "anthropic":
            return cls._init_anthropic(timeout)
        else:
            return cls._init_ollama(timeout)

    @classmethod
    def _from_config(cls, config: dict) -> Optional["FactExtractor"]:
        """Create a fact extractor from a per-tenant config dict."""
        provider = config.get("llm_provider", "ollama").lower().strip()
        timeout = int(config.get("timeout", 60))

        if cls._semaphore is None:
            max_concurrent = int(os.environ.get("OCTOPODA_LLM_MAX_CONCURRENT", "2"))
            cls._semaphore = threading.Semaphore(max_concurrent)

        if provider == "none":
            return None

        instance = cls()
        instance._timeout = timeout

        if provider == "platform":
            # Platform free tier — uses Octopoda's shared key
            platform_key = os.environ.get("OCTOPODA_PLATFORM_OPENAI_KEY", "")
            if not platform_key:
                return None  # platform key not configured on this server
            instance._provider = "openai"  # uses same OpenAI extraction logic
            instance._openai_key = platform_key
            instance._openai_model = "gpt-4o-mini"
            instance._openai_base_url = "https://api.openai.com/v1"
            instance._available = True
            return instance

        elif provider == "openai":
            api_key = config.get("openai_api_key", "")
            if not api_key:
                return cls._init_ollama(timeout)  # fallback
            instance._provider = "openai"
            instance._openai_key = api_key
            instance._openai_model = config.get("openai_model", "gpt-4o-mini")
            instance._openai_base_url = config.get("openai_base_url", "https://api.openai.com/v1")
            instance._available = True
            return instance

        elif provider == "anthropic":
            api_key = config.get("anthropic_api_key", "")
            if not api_key:
                return cls._init_ollama(timeout)  # fallback
            instance._provider = "anthropic"
            instance._anthropic_key = api_key
            instance._anthropic_model = config.get("anthropic_model", "claude-haiku-4-5-20251001")
            instance._available = True
            return instance

        else:  # ollama
            return cls._init_ollama(timeout)

    @classmethod
    def _init_platform(cls, timeout: int) -> Optional["FactExtractor"]:
        """Initialize with platform shared OpenAI key (free tier)."""
        platform_key = os.environ.get("OCTOPODA_PLATFORM_OPENAI_KEY", "")
        if not platform_key:
            # No platform key configured — fall back to none
            cls._instance = cls()
            return None

        instance = cls()
        instance._provider = "openai"  # reuses OpenAI extraction logic
        instance._openai_key = platform_key
        instance._openai_model = "gpt-4o-mini"
        instance._openai_base_url = "https://api.openai.com/v1"
        instance._available = True
        instance._timeout = timeout
        cls._instance = instance
        return instance

    @classmethod
    def _init_ollama(cls, timeout: int) -> Optional["FactExtractor"]:
        """Initialize with Ollama backend."""
        ollama_url = os.environ.get("OCTOPODA_OLLAMA_URL", "http://localhost:11434")
        model_name = os.environ.get("OCTOPODA_OLLAMA_MODEL", "llama3.2")

        try:
            import requests
            resp = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if resp.status_code != 200:
                cls._instance = cls()
                return None
        except Exception:
            cls._instance = cls()
            return None

        instance = cls()
        instance._provider = "ollama"
        instance._ollama_url = ollama_url
        instance._model_name = model_name
        instance._available = True
        instance._timeout = timeout
        cls._instance = instance
        return instance

    @classmethod
    def _init_openai(cls, timeout: int) -> Optional["FactExtractor"]:
        """Initialize with OpenAI backend."""
        api_key = os.environ.get("OCTOPODA_OPENAI_API_KEY", "")
        if not api_key:
            # Fall back to Ollama
            return cls._init_ollama(timeout)

        instance = cls()
        instance._provider = "openai"
        instance._openai_key = api_key
        instance._openai_model = os.environ.get("OCTOPODA_OPENAI_MODEL", "gpt-4o-mini")
        instance._openai_base_url = os.environ.get("OCTOPODA_OPENAI_BASE_URL", "https://api.openai.com/v1")
        instance._available = True
        instance._timeout = timeout
        cls._instance = instance
        return instance

    @classmethod
    def _init_anthropic(cls, timeout: int) -> Optional["FactExtractor"]:
        """Initialize with Anthropic backend."""
        api_key = os.environ.get("OCTOPODA_ANTHROPIC_API_KEY", "")
        if not api_key:
            # Fall back to Ollama
            return cls._init_ollama(timeout)

        instance = cls()
        instance._provider = "anthropic"
        instance._anthropic_key = api_key
        instance._anthropic_model = os.environ.get(
            "OCTOPODA_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"
        )
        instance._available = True
        instance._timeout = timeout
        cls._instance = instance
        return instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None
        cls._semaphore = None

    def extract_facts(self, text: str) -> FactExtractionResult:
        """Extract structured facts from text using the configured LLM provider.

        Uses a semaphore to limit concurrent LLM calls and prevent overload.
        Falls back to returning the raw text if extraction fails.
        """
        if not text or not text.strip():
            return FactExtractionResult(
                facts=[], source_text=text,
                extraction_time_ms=0, used_llm=False, provider="none",
            )

        # Skip very short text (not worth decomposing)
        if len(text.split()) < 4:
            return FactExtractionResult(
                facts=[text], source_text=text,
                extraction_time_ms=0, used_llm=False, provider="none",
            )

        # Acquire semaphore (blocks if too many concurrent calls)
        semaphore = self.__class__._semaphore
        if semaphore and not semaphore.acquire(timeout=self._timeout):
            # Couldn't acquire in time — return raw text
            return FactExtractionResult(
                facts=[text], source_text=text,
                extraction_time_ms=0, used_llm=False, provider="timeout",
            )

        try:
            if self._provider == "openai":
                return self._extract_openai(text)
            elif self._provider == "anthropic":
                return self._extract_anthropic(text)
            else:
                return self._extract_ollama(text)
        finally:
            if semaphore:
                semaphore.release()

    def _extract_ollama(self, text: str) -> FactExtractionResult:
        """Extract facts using Ollama."""
        import requests

        prompt = EXTRACTION_PROMPT.format(text=text)
        start = time.perf_counter()

        try:
            resp = requests.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": self._model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 400},
                },
                timeout=self._timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return FactExtractionResult(
                    facts=[text], source_text=text,
                    extraction_time_ms=elapsed_ms, used_llm=False, provider="ollama",
                )

            raw = resp.json().get("response", "")
            facts = self._parse_facts(raw)

            return FactExtractionResult(
                facts=facts if facts else [text],
                source_text=text,
                extraction_time_ms=elapsed_ms,
                used_llm=bool(facts),
                provider="ollama",
            )

        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return FactExtractionResult(
                facts=[text], source_text=text,
                extraction_time_ms=elapsed_ms, used_llm=False, provider="ollama",
            )

    def _extract_openai(self, text: str) -> FactExtractionResult:
        """Extract facts using OpenAI API."""
        import requests

        prompt = EXTRACTION_PROMPT.format(text=text)
        start = time.perf_counter()

        try:
            resp = requests.post(
                f"{self._openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._openai_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 400,
                },
                timeout=self._timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return FactExtractionResult(
                    facts=[text], source_text=text,
                    extraction_time_ms=elapsed_ms, used_llm=False, provider="openai",
                )

            raw = resp.json()["choices"][0]["message"]["content"]
            facts = self._parse_facts(raw)

            return FactExtractionResult(
                facts=facts if facts else [text],
                source_text=text,
                extraction_time_ms=elapsed_ms,
                used_llm=bool(facts),
                provider="openai",
            )

        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return FactExtractionResult(
                facts=[text], source_text=text,
                extraction_time_ms=elapsed_ms, used_llm=False, provider="openai",
            )

    def _extract_anthropic(self, text: str) -> FactExtractionResult:
        """Extract facts using Anthropic API."""
        import requests

        prompt = EXTRACTION_PROMPT.format(text=text)
        start = time.perf_counter()

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._anthropic_model,
                    "max_tokens": 400,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
                timeout=self._timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return FactExtractionResult(
                    facts=[text], source_text=text,
                    extraction_time_ms=elapsed_ms, used_llm=False, provider="anthropic",
                )

            raw = resp.json()["content"][0]["text"]
            facts = self._parse_facts(raw)

            return FactExtractionResult(
                facts=facts if facts else [text],
                source_text=text,
                extraction_time_ms=elapsed_ms,
                used_llm=bool(facts),
                provider="anthropic",
            )

        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return FactExtractionResult(
                facts=[text], source_text=text,
                extraction_time_ms=elapsed_ms, used_llm=False, provider="anthropic",
            )

    @staticmethod
    def _parse_facts(raw: str) -> List[str]:
        """Parse a JSON array of fact strings from LLM output."""
        try:
            start_idx = raw.find("[")
            end_idx = raw.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                facts = json.loads(raw[start_idx:end_idx])
                if isinstance(facts, list):
                    return [f for f in facts if isinstance(f, str) and f.strip()]
        except (json.JSONDecodeError, ValueError):
            pass
        return []
