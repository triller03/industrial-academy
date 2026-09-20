"""AI Mentor LLM layer tests.

Standalone unit tests (no live server, no API keys). The provider layer is
exercised with a mocked HTTP transport; the hybrid engine is exercised with a
fake client and the deterministic fallback.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.mentor.engine import HybridMentorEngine, MentorRequest  # noqa: E402
from app.mentor.llm import AIMentorClient, LLMError  # noqa: E402


def _client(provider: str = "openai", key: str = "k-test", base: str = "", model: str = "") -> AIMentorClient:
    return AIMentorClient(provider=provider, api_key=key, base_url=base, model=model)


class _FakeResponse:
    def __init__(self, status: int = 200, payload: dict | None = None):
        self.status_code = status
        self._payload = payload or {
            "choices": [{"message": {"content": "Trace the loop in four steps."}}]
        }
        self.text = json.dumps(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")
        return None

    def json(self):
        return self._payload


class LLMPayloadTests(unittest.TestCase):
    def _mock_httpx(self):
        """httpx.Client is used as a context manager; make the mock's __enter__ return itself."""
        p = mock.patch("httpx.Client")
        mk = p.start()
        self.addCleanup(p.stop)
        mk.return_value.__enter__.return_value = mk.return_value
        mk.return_value.__exit__.return_value = False
        return mk

    def test_openai_compatible_payload(self):
        client = _client("openai")
        mk = self._mock_httpx()
        mk.return_value.post.return_value = _FakeResponse()
        text = client.chat("sys", [{"role": "user", "content": "hi"}], model="gpt-x")
        self.assertEqual(text, "Trace the loop in four steps.")
        kwargs = mk.return_value.post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer k-test")
        self.assertEqual(kwargs["json"]["messages"][0], {"role": "system", "content": "sys"})
        self.assertEqual(kwargs["json"]["model"], "gpt-x")

    def test_openrouter_adds_headers_and_uses_its_base(self):
        client = _client("openrouter", base="https://openrouter.ai/api/v1")
        self.assertEqual(client.base_url, "https://openrouter.ai/api/v1")
        self.assertIn("gpt-4o-mini", client.model)
        mk = self._mock_httpx()
        mk.return_value.post.return_value = _FakeResponse()
        client.chat("sys", [{"role": "user", "content": "hi"}])
        kwargs = mk.return_value.post.call_args.kwargs
        self.assertIn("HTTP-Referer", kwargs["headers"])
        self.assertIn("https://openrouter.ai/api/v1/chat/completions", mk.return_value.post.call_args.args[0])

    def test_anthropic_payload(self):
        client = _client("anthropic")
        mk = self._mock_httpx()
        mk.return_value.post.return_value = _FakeResponse(
            payload={"content": [{"type": "text", "text": "Claude answer"}]}
        )
        text = client.chat("sys", [{"role": "user", "content": "hi"}])
        self.assertEqual(text, "Claude answer")
        kwargs = mk.return_value.post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["x-api-key"], "k-test")
        self.assertEqual(kwargs["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(kwargs["json"]["system"], "sys")

    def test_gemini_payload(self):
        client = _client("gemini")
        mk = self._mock_httpx()
        mk.return_value.post.return_value = _FakeResponse(
            payload={"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]}
        )
        text = client.chat("sys", [{"role": "user", "content": "hi"}], model="gemini-flash")
        self.assertEqual(text, "Gemini answer")
        call = mk.return_value.post.call_args
        self.assertIn("/v1beta/models/gemini-flash:generateContent", call.args[0])
        self.assertEqual(call.kwargs["params"]["key"], "k-test")
        self.assertEqual(call.kwargs["json"]["systemInstruction"]["parts"][0]["text"], "sys")

    def test_ollama_defaults_and_no_auth(self):
        client = _client("ollama", key="")
        self.assertEqual(client.base_url, "http://127.0.0.1:11434/v1")
        self.assertTrue(client.enabled)
        mk = self._mock_httpx()
        mk.return_value.post.return_value = _FakeResponse()
        client.chat("sys", [{"role": "user", "content": "hi"}])
        headers = mk.return_value.post.call_args.kwargs.get("headers", {})
        self.assertNotIn("Authorization", headers)

    def test_provider_error_raises_llmerror(self):
        client = _client("openai")
        mk = self._mock_httpx()
        mk.return_value.post.return_value = _FakeResponse(status=429)
        with self.assertRaises(LLMError):
            client.chat("sys", [{"role": "user", "content": "hi"}])

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            _client("skynet")

    def test_history_coalescing(self):
        from app.mentor import llm as llm_mod

        turns = llm_mod._normalize_turns(
            [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
                {"role": "assistant", "content": "c"},
                {"role": "system", "content": "meta"},
                {"role": "user", "content": ""},
                {"role": "user", "content": "d"},
            ]
        )
        self.assertEqual(
            turns,
            [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b\nc"}, {"role": "user", "content": "d"}],
        )


class HybridEngineTests(unittest.TestCase):
    def _fake_llm(self, text: str = "reasoned answer"):
        f = mock.Mock()
        f.enabled = True
        f.provider = "openai"
        f.model = "gpt-think"
        f.chat.return_value = text
        return f

    def test_uses_llm_reply_when_enabled(self):
        eng = HybridMentorEngine(llm=self._fake_llm())
        resp = eng.respond(MentorRequest("why is the pump not starting?", topic="pump"))
        self.assertEqual(resp.reply, "reasoned answer")
        self.assertEqual(resp.mode, "socratic")
        self.assertEqual(resp.level, 1)

    def test_safety_never_reaches_llm(self):
        llm = self._fake_llm()
        eng = HybridMentorEngine(llm=llm)
        resp = eng.respond(MentorRequest("should I open the live panel?"))
        self.assertTrue(resp.safety_triggered)
        self.assertEqual(resp.mode, "safety")
        self.assertIn("STOP", resp.reply)
        llm.chat.assert_not_called()

    def test_llm_failure_falls_back_to_rule_engine(self):
        llm = self._fake_llm()
        llm.chat.side_effect = LLMError("boom")
        eng = HybridMentorEngine(llm=llm)
        resp = eng.respond(MentorRequest("why is the pump not starting?", topic="pump"))
        self.assertEqual(resp.mode, "socratic")
        self.assertTrue(resp.reply)
        self.assertIn("?", resp.reply)

    def test_guided_mode_keeps_gate_semantics(self):
        eng = HybridMentorEngine(llm=self._fake_llm())
        resp = eng.respond(MentorRequest("give me the answer"))
        self.assertEqual(resp.mode, "guided")

    def test_disabled_llm_is_deterministic(self):
        llm = mock.Mock()
        llm.enabled = False
        llm.provider = ""
        llm.model = ""
        eng = HybridMentorEngine(llm=llm)
        resp = eng.respond(MentorRequest("why is the pump not starting?", topic="pump"))
        self.assertIn(resp.mode, ("socratic", "guided"))
        self.assertFalse(eng.status()["enabled"])

    def test_solution_uses_llm_in_full_mode(self):
        llm = self._fake_llm("here is the complete walkthrough")
        eng = HybridMentorEngine(llm=llm)
        resp = eng.solution("full solution please", "pump start failure", 4)
        self.assertEqual(resp.reply, "here is the complete walkthrough")
        self.assertEqual(resp.level, 4)
        self.assertEqual(eng.status()["model"], "gpt-think")


class FromSettingsTests(unittest.TestCase):
    def test_settings_default_to_rule_based(self):
        class _S:
            ai_provider = ""
            ai_api_key = ""
            ai_base_url = ""
            ai_model = ""
            ai_max_tokens = 900
            ai_timeout_seconds = 60
            ai_temperature = 0.7

        client = AIMentorClient.from_settings(_S())
        self.assertFalse(client.enabled)


# ---- modern runner -------------------------------------------------------
def run():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(run())