"""Generic LLM client for chat completions and embeddings.

Sibling of :class:`LLMAnalyzer`; reuses the same provider/Azure/API-key
resolution but exposes generic primitives needed by the personas package
(arbitrary prompts, JSON-mode responses, token usage, embeddings).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CompletionResult:
    """Result of a chat completion."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class EmbeddingResult:
    """Result of an embedding call."""

    vectors: list[list[float]]
    prompt_tokens: int = 0
    model: str = ""


class LLMClient:
    """Generic provider-agnostic client for chat + embeddings."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.provider: str = config.get("provider", "openai")
        self.model: str = config.get("model", "gpt-4o")
        self.embedding_model: str = config.get(
            "embedding_model", "text-embedding-3-small"
        )

        # Azure settings
        self.azure_endpoint: str = config.get("azure_endpoint", "") or os.environ.get(
            "AZURE_OPENAI_ENDPOINT", ""
        )
        self.azure_api_version: str = config.get(
            "azure_api_version", ""
        ) or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self.azure_deployment: str = config.get("azure_deployment", "") or self.model
        self.azure_embedding_deployment: str = (
            config.get("azure_embedding_deployment", "") or self.embedding_model
        )

        self.api_key: str = (
            config.get("api_key", "")
            or os.environ.get("AZURE_OPENAI_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )

        # Auto-detect Azure when an Azure endpoint + Azure key are present but
        # the config still says "openai" (common when reusing default config).
        if (
            self.provider != "azure"
            and self.azure_endpoint
            and os.environ.get("AZURE_OPENAI_API_KEY")
        ):
            self.provider = "azure"

    @property
    def is_available(self) -> bool:
        if self.provider == "azure":
            return bool(self.api_key and self.azure_endpoint)
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Chat completions
    # ------------------------------------------------------------------

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        json_mode: bool = False,
        model: Optional[str] = None,
    ) -> CompletionResult:
        """Run a chat completion and return text + token usage."""
        chosen_model = model or self.model
        client = self._chat_client()
        kwargs: dict[str, Any] = {
            "model": (
                self.azure_deployment if self.provider == "azure" else chosen_model
            ),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        return CompletionResult(
            text=response.choices[0].message.content or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            model=chosen_model,
        )

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Return embedding vectors for the given texts (single batch)."""
        if not texts:
            return EmbeddingResult(vectors=[], model=self.embedding_model)

        client = self._embeddings_client()
        model_name = (
            self.azure_embedding_deployment
            if self.provider == "azure"
            else self.embedding_model
        )
        response = client.embeddings.create(model=model_name, input=texts)
        usage = getattr(response, "usage", None)
        return EmbeddingResult(
            vectors=[item.embedding for item in response.data],
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            model=self.embedding_model,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _chat_client(self):
        if self.provider == "azure":
            from openai import AzureOpenAI

            return AzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.azure_endpoint,
                api_version=self.azure_api_version,
            )
        from openai import OpenAI

        return OpenAI(api_key=self.api_key)

    def _embeddings_client(self):
        # Same client classes expose embeddings.
        return self._chat_client()
