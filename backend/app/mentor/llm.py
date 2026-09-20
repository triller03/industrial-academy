"""Provider-agnostic LLM client for the AI Mentor.

Supported backends (all optional, selected via settings):
    openai      -> OpenAI Chat Completions            https://api.openai.com/v1
    openrouter  -> OpenRouter (runtime model switching) https://openrouter.ai/api/v1
    ollama      -> local Ollama (offline)             http://127.0.0.1:11434/v1
    anthropic   -> Claude Messages API                https://api.anthropic.com/v1
    gemini      -> Google Generative Language API     https://generativelanguage.googleapis.com

Any OpenAI-compatible endpoint can be pointed at via ai_base_url
(Ollama, vLLM, Groq, DeepSeek, LM Studio, …). Selection + defaults live in
AIMentorClient.from_settings(). The model never sees safety-critical prompts:
the deterministic guard in the mentor engine short-circuits before calling us.
"""

from __future__ import annotations

import httpx

PROVIDER_DEFAULTS = {
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "ollama": ("http://127.0.0.1:11434/v1", "llama3.2"),
    "anthropic": ("https://api.anthropic.com/v1", "claude-3-5-sonnet-latest"),
    "gemini": ("https://generativelanguage.googleapis.com", "gemini-2.0-flash"),
}

OPENROUTER_TITLE = "ASAP.A - Industrial Automation Training Platform"


class LLMError(Exception):
    """Raised when the provider is unreachable or refuses the request."""


class AIMentorClient:
    """Thin synchronous wrapper around a configured LLM provider."""

    def __init__(
        self,
        provider: str = "",
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        max_tokens: int = 900,
        timeout_seconds: int = 60,
        temperature: float = 0.7,
    ):
        provider = (provider or "").strip().lower()
        if provider and provider not in PROVIDER_DEFAULTS:
            raise ValueError(f"unknown ai_provider: {provider!r}")
        self.provider = provider
        self.api_key = api_key
        default_base, default_model = PROVIDER_DEFAULTS.get(provider, ("", ""))
        self.base_url = (base_url or default_base).rstrip("/")
        self.model = model or default_model
        self.max_tokens = max_tokens
        self.timeout = httpx.Timeout(timeout_seconds)
        self.temperature = temperature

    # ----- public -------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return bool(self.provider)

    @classmethod
    def from_settings(cls, settings) -> "AIMentorClient":
        return cls(
            provider=settings.ai_provider,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            model=settings.ai_model,
            max_tokens=settings.ai_max_tokens,
            timeout_seconds=settings.ai_timeout_seconds,
            temperature=settings.ai_temperature,
        )

    def chat(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
    ) -> str:
        """Send a turn and return the assistant text. Raises LLMError on failure."""
        if not self.enabled:
            raise LLMError("no AI provider configured")
        chosen = model or self.model
        try:
            with httpx.Client(timeout=self.timeout) as client:
                if self.provider == "anthropic":
                    return self._anthropic(client, system, messages, chosen)
                if self.provider == "gemini":
                    return self._gemini(client, system, messages, chosen)
                return self._openai_compatible(client, system, messages, chosen)
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.provider} request failed: {exc}") from exc

    # ----- providers ----------------------------------------------------
    def _openai_compatible(
        self, client: httpx.Client, system: str, messages: list[dict], model: str
    ) -> str:
        turns = [{"role": "system", "content": system}] + _normalize_turns(messages)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/triller03/industrial-academy"
            headers["X-Title"] = OPENROUTER_TITLE
        payload = {
            "model": model,
            "messages": turns,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        resp = client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        return _extract(resp, lambda j: j["choices"][0]["message"]["content"])

    def _anthropic(
        self, client: httpx.Client, system: str, messages: list[dict], model: str
    ) -> str:
        payload = {
            "model": model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": _normalize_turns(messages),
        }
        resp = client.post(
            f"{self.base_url}/messages",
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        return _extract(resp, lambda j: "".join(b.get("text", "") for b in j["content"]))

    def _gemini(
        self, client: httpx.Client, system: str, messages: list[dict], model: str
    ) -> str:
        contents = []
        for turn in _normalize_turns(messages):
            contents.append(
                {"role": "model" if turn["role"] == "assistant" else "user",
                 "parts": [{"text": turn["content"]}]}
            )
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "temperature": self.temperature,
            },
        }
        params = {"key": self.api_key}
        resp = client.post(
            f"{self.base_url}/v1beta/models/{model}:generateContent",
            json=payload,
            params=params,
        )
        return _extract(resp, lambda j: j["candidates"][0]["content"]["parts"][0]["text"])


def _normalize_turns(messages: list[dict]) -> list[dict]:
    """Coalesce history into alternating user/assistant turns."""
    turns: list[dict] = []
    for msg in messages or []:
        role = msg.get("role")
        if role not in ("user", "assistant"):  # drop system/mentor meta rows
            continue
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n" + text
        else:
            turns.append({"role": role, "content": text})
    return turns


def _extract(resp: httpx.Response, pick) -> str:
    try:
        resp.raise_for_status()
        data = resp.json()
        text = pick(data)
    except Exception as exc:
        body = resp.text[:300] if resp.text else ""
        raise LLMError(f"provider error {resp.status_code}: {body or exc}") from exc
    text = (text or "").strip()
    if not text:
        raise LLMError("provider returned an empty reply")
    return text