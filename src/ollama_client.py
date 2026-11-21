"""Tiny Ollama HTTP client (no external SDK needed)."""
import os
import httpx

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen2.5:1.5b")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")


def chat(messages, model=None, temperature=0.2, timeout=120):
    """Send chat messages to Ollama and return the assistant text."""
    resp = httpx.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": model or CHAT_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def embed(text, model=None, timeout=60):
    """Embed a single string with Ollama."""
    resp = httpx.post(
        f"{OLLAMA_HOST}/api/embeddings",
        json={"model": model or EMBED_MODEL, "prompt": text},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]
