"""Ollama LLM client — sends prompts to a local Ollama instance."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    """Configuration for the Ollama connection."""
    base_url: str = "http://localhost:11434"
    model: str = "llama3"
    temperature: float = 0.1  # Low temperature for deterministic structured output
    timeout: int = 120  # Seconds


class OllamaError(Exception):
    """Raised when the Ollama API returns an error."""
    pass


class OllamaClient:
    """Minimal Ollama REST API client (no external dependencies)."""

    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig()

    def chat(self, messages: list[dict], system: str | None = None) -> str:
        """
        Send a chat completion request and return the assistant's reply.
        
        Uses the /api/chat endpoint with stream=false.
        """
        if system:
            messages = [{"role": "system", "content": system}] + messages

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
            },
        }

        result = self._post("/api/chat", payload)
        return result["message"]["content"]

    def is_available(self) -> bool:
        """Check if Ollama is reachable and the model is loaded."""
        try:
            self._get("/api/tags")
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """Return a list of available model names."""
        try:
            data = self._get("/api/tags")
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal HTTP helpers (stdlib only, no requests/httpx needed)
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.config.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise OllamaError(
                f"Cannot reach Ollama at {self.config.base_url}. "
                f"Is Ollama running? (ollama serve)\n  Error: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise OllamaError(f"Invalid JSON response from Ollama: {e}") from e

    def _get(self, path: str) -> dict:
        url = f"{self.config.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise OllamaError(
                f"Cannot reach Ollama at {self.config.base_url}. "
                f"Is Ollama running? (ollama serve)\n  Error: {e}"
            ) from e
