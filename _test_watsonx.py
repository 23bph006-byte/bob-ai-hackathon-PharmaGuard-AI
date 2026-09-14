"""
Tests for IBM watsonx.ai integration in PharmaGuard AI Copilot.

All HTTP calls are mocked — no live IBM API is required.
Tests verify:
  - Frankfurt (eu-de) is the default endpoint
  - Correct default model ID
  - Credential detection (env vars and Streamlit secrets)
  - No credential leakage in error messages
  - Successful watsonx response is returned and labelled correctly
  - API failure triggers rule-based fallback, not a crash
  - Missing credentials → fallback (never watsonx)
  - Full PharmaGuard context is passed to the model
  - Mode label is "IBM watsonx.ai / Granite" on success
"""

import sys
import os
import json
import types
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")

# ── Minimal Streamlit shim ─────────────────────────────────────────────────────
_ss: dict = {}

class _FakeSecrets:
    def __init__(self, data=None):
        self._data = data or {}
    def get(self, key, default=None):
        return self._data.get(key, default)

_fake_secrets = _FakeSecrets()

class _FakeST(types.ModuleType):
    session_state = _ss
    def markdown(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def success(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def caption(self, *a, **kw): pass
    def columns(self, *a, **kw): return [self] * max((a[0] if a else 1), 1)
    def __enter__(self): return self
    def __exit__(self, *a): pass
    @property
    def secrets(self): return _fake_secrets

_fake_st = _FakeST("streamlit")
sys.modules["streamlit"] = _fake_st

import pandas as pd

# Import the module under test AFTER the shim is in place
from pages.ai_copilot import (
    _call_watsonx,
    _detect_ai_provider,
    _get_secret,
    _WATSONX_DEFAULT_URL,
    _WATSONX_DEFAULT_MODEL_ID,
    query_ai,
    build_safety_context,
    build_regulatory_context,
    _build_llm_context_block,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _inject_safety():
    # Signal_Status must start with "⚠️" to be detected as a potential signal
    _ss["signal_results"] = pd.DataFrame([
        {"Drug": "Atorvastatin", "Adverse_Event": "Myopathy",
         "a": 5, "b": 7, "c": 1, "d": 87,
         "PRR": 36.667, "Chi_Square": 30.757,
         "Signal_Status": "\u26a0\ufe0f Potential Signal"},
    ])

def _inject_regulatory():
    _ss["readiness_df"] = pd.DataFrame([
        {"Module": "Module 1", "Document": "Application form",    "Status": "Present"},
        {"Module": "Module 3", "Document": "Process validation",  "Status": "Missing"},
    ])

def _mock_iam_response(token: str = "test-bearer-token") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"access_token": token}
    return resp

def _mock_gen_response(text: str = "Mocked Granite response text.") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"results": [{"generated_text": text}]}
    return resp


# ══════════════════════════════════════════════════════════════════════════════
class TestWatsonxDefaults(unittest.TestCase):
    """Verify Frankfurt endpoint and correct model are the defaults."""

    def test_default_url_is_frankfurt(self):
        self.assertEqual(_WATSONX_DEFAULT_URL, "https://eu-de.ml.cloud.ibm.com")
        self.assertNotIn("us-south", _WATSONX_DEFAULT_URL)
        self.assertNotIn("us-east",  _WATSONX_DEFAULT_URL)
        self.assertIn("eu-de", _WATSONX_DEFAULT_URL)

    def test_default_model_is_granite(self):
        self.assertIn("granite", _WATSONX_DEFAULT_MODEL_ID)
        self.assertEqual(_WATSONX_DEFAULT_MODEL_ID, "ibm/granite-3-8b-instruct")

    def test_default_url_used_when_env_absent(self):
        """When WATSONX_URL env var is absent, Frankfurt URL must be used."""
        os.environ.pop("WATSONX_URL", None)
        os.environ.pop("WATSONX_API_KEY", None)
        os.environ.pop("WATSONX_PROJECT_ID", None)

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("Hello from Granite"),
            ]
            try:
                result = _call_watsonx.__wrapped__("test prompt", "test system") \
                    if hasattr(_call_watsonx, "__wrapped__") else None
            except Exception:
                pass

            # Confirm that when called with env vars set, Frankfurt endpoint is used
            os.environ["WATSONX_API_KEY"]    = "dummy-key"
            os.environ["WATSONX_PROJECT_ID"] = "dummy-project"
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("Hello from Frankfurt"),
            ]
            _call_watsonx("test prompt", "test system")

            # Second call (generation) must target eu-de
            gen_call_url = mock_post.call_args_list[1][0][0]
            self.assertIn("eu-de.ml.cloud.ibm.com", gen_call_url)
            self.assertNotIn("us-south", gen_call_url)

        os.environ.pop("WATSONX_API_KEY", None)
        os.environ.pop("WATSONX_PROJECT_ID", None)


class TestCredentialDetection(unittest.TestCase):
    """_detect_ai_provider() must read secrets/env vars, never hard-coded values."""

    def setUp(self):
        for key in ("WATSONX_API_KEY", "WATSONX_PROJECT_ID", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        _fake_secrets._data = {}

    def test_no_credentials_returns_fallback(self):
        self.assertEqual(_detect_ai_provider(), "fallback")

    def test_watsonx_env_vars_detected(self):
        os.environ["WATSONX_API_KEY"]    = "key123"
        os.environ["WATSONX_PROJECT_ID"] = "proj456"
        self.assertEqual(_detect_ai_provider(), "watsonx")
        os.environ.pop("WATSONX_API_KEY")
        os.environ.pop("WATSONX_PROJECT_ID")

    def test_watsonx_streamlit_secrets_detected(self):
        _fake_secrets._data = {
            "WATSONX_API_KEY":    "key-from-secrets",
            "WATSONX_PROJECT_ID": "proj-from-secrets",
        }
        self.assertEqual(_detect_ai_provider(), "watsonx")
        _fake_secrets._data = {}

    def test_only_api_key_without_project_id_is_fallback(self):
        os.environ["WATSONX_API_KEY"] = "key-only"
        self.assertEqual(_detect_ai_provider(), "fallback")
        os.environ.pop("WATSONX_API_KEY")

    def test_openai_detected(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        self.assertEqual(_detect_ai_provider(), "openai")
        os.environ.pop("OPENAI_API_KEY")

    def test_watsonx_takes_priority_over_openai(self):
        os.environ["WATSONX_API_KEY"]    = "wx-key"
        os.environ["WATSONX_PROJECT_ID"] = "wx-proj"
        os.environ["OPENAI_API_KEY"]     = "oai-key"
        self.assertEqual(_detect_ai_provider(), "watsonx")
        for k in ("WATSONX_API_KEY", "WATSONX_PROJECT_ID", "OPENAI_API_KEY"):
            os.environ.pop(k, None)


class TestCallWatsonx(unittest.TestCase):
    """Test the _call_watsonx function with mocked HTTP."""

    def setUp(self):
        os.environ["WATSONX_API_KEY"]    = "test-api-key"
        os.environ["WATSONX_PROJECT_ID"] = "test-project-id"
        os.environ.pop("WATSONX_URL", None)
        os.environ.pop("WATSONX_MODEL_ID", None)

    def tearDown(self):
        for k in ("WATSONX_API_KEY", "WATSONX_PROJECT_ID", "WATSONX_URL", "WATSONX_MODEL_ID"):
            os.environ.pop(k, None)

    def test_successful_call_returns_generated_text(self):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response("bearer-abc"),
                _mock_gen_response("Granite says: This is a safety signal."),
            ]
            result = _call_watsonx("What is PRR?", "You are a pharmacovigilance assistant.")
        self.assertEqual(result, "Granite says: This is a safety signal.")

    def test_iam_call_uses_global_endpoint(self):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            _call_watsonx("test", "system")
            iam_url = mock_post.call_args_list[0][0][0]
            self.assertIn("iam.cloud.ibm.com", iam_url)

    def test_gen_call_uses_frankfurt_by_default(self):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            _call_watsonx("test", "system")
            gen_url = mock_post.call_args_list[1][0][0]
            self.assertIn("eu-de.ml.cloud.ibm.com", gen_url)
            self.assertNotIn("us-south", gen_url)

    def test_watsonx_url_env_var_overrides_default(self):
        os.environ["WATSONX_URL"] = "https://us-south.ml.cloud.ibm.com"
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            _call_watsonx("test", "system")
            gen_url = mock_post.call_args_list[1][0][0]
            self.assertIn("us-south.ml.cloud.ibm.com", gen_url)

    def test_model_id_is_granite_by_default(self):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            _call_watsonx("test", "system")
            payload = mock_post.call_args_list[1][1]["json"]
            self.assertIn("granite", payload["model_id"])

    def test_model_id_env_var_overrides_default(self):
        os.environ["WATSONX_MODEL_ID"] = "ibm/granite-13b-instruct-v2"
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            _call_watsonx("test", "system")
            payload = mock_post.call_args_list[1][1]["json"]
            self.assertEqual(payload["model_id"], "ibm/granite-13b-instruct-v2")

    def test_project_id_in_payload(self):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            _call_watsonx("test", "system")
            payload = mock_post.call_args_list[1][1]["json"]
            self.assertEqual(payload["project_id"], "test-project-id")

    def test_api_key_not_in_error_message(self):
        """Credential leakage test: API key must NOT appear in raised exception."""
        with patch("requests.post") as mock_post:
            iam_fail = MagicMock()
            iam_fail.raise_for_status.side_effect = Exception("401 Unauthorized")
            mock_post.return_value = iam_fail

            try:
                _call_watsonx("test", "system")
                self.fail("Expected RuntimeError was not raised")
            except RuntimeError as exc:
                err_text = str(exc)
                self.assertNotIn("test-api-key", err_text,
                                 "API key must NOT appear in error message")

    def test_iam_failure_raises_runtime_error(self):
        with patch("requests.post") as mock_post:
            iam_fail = MagicMock()
            iam_fail.raise_for_status.side_effect = Exception("Connection error")
            mock_post.return_value = iam_fail

            with self.assertRaises(RuntimeError) as ctx:
                _call_watsonx("test", "system")
            self.assertIn("IAM token exchange failed", str(ctx.exception))

    def test_generation_failure_raises_runtime_error(self):
        with patch("requests.post") as mock_post:
            gen_fail = MagicMock()
            gen_fail.raise_for_status.side_effect = Exception("503 Service Unavailable")
            mock_post.side_effect = [_mock_iam_response(), gen_fail]

            with self.assertRaises(RuntimeError) as ctx:
                _call_watsonx("test", "system")
            self.assertIn("generation request failed", str(ctx.exception))


class TestQueryAiFallbackOnError(unittest.TestCase):
    """query_ai must fall back to rule-based mode when watsonx call fails."""

    def setUp(self):
        os.environ["WATSONX_API_KEY"]    = "key"
        os.environ["WATSONX_PROJECT_ID"] = "proj"
        _ss.clear()
        _inject_safety()
        _inject_regulatory()

    def tearDown(self):
        os.environ.pop("WATSONX_API_KEY", None)
        os.environ.pop("WATSONX_PROJECT_ID", None)

    def test_watsonx_failure_falls_back_not_crashes(self):
        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()

        with patch("requests.post") as mock_post:
            iam_fail = MagicMock()
            iam_fail.raise_for_status.side_effect = Exception("Network timeout")
            mock_post.return_value = iam_fail

            response, mode = query_ai(
                "Summarise the current safety signal analysis.",
                s_ctx, r_ctx, "watsonx",
            )

        # Must fall back gracefully — not crash, return non-empty text
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 50)
        self.assertEqual(mode, "Rule-based fallback")

    def test_successful_watsonx_returns_granite_label(self):
        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("IBM Granite response about safety signals."),
            ]
            response, mode = query_ai(
                "What safety signals were detected?",
                s_ctx, r_ctx, "watsonx",
            )

        self.assertEqual(response, "IBM Granite response about safety signals.")
        self.assertEqual(mode, "IBM watsonx.ai / Granite")


class TestContextPassedToModel(unittest.TestCase):
    """Verify actual PharmaGuard data is included in the prompt sent to Granite."""

    def setUp(self):
        os.environ["WATSONX_API_KEY"]    = "key"
        os.environ["WATSONX_PROJECT_ID"] = "proj"
        _ss.clear()
        _inject_safety()
        _inject_regulatory()

    def tearDown(self):
        os.environ.pop("WATSONX_API_KEY", None)
        os.environ.pop("WATSONX_PROJECT_ID", None)

    def test_drug_name_in_prompt(self):
        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            query_ai("What signals were found?", s_ctx, r_ctx, "watsonx")

            payload = mock_post.call_args_list[1][1]["json"]
            prompt_text = payload["input"]
            self.assertIn("Atorvastatin", prompt_text)

    def test_prr_value_in_prompt(self):
        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            query_ai("Explain the PRR.", s_ctx, r_ctx, "watsonx")

            payload = mock_post.call_args_list[1][1]["json"]
            prompt_text = payload["input"]
            self.assertIn("36.667", prompt_text)

    def test_readiness_score_in_prompt(self):
        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            query_ai("What is the readiness score?", s_ctx, r_ctx, "watsonx")

            payload = mock_post.call_args_list[1][1]["json"]
            prompt_text = payload["input"]
            self.assertIn(str(r_ctx["score_pct"]), prompt_text)

    def test_missing_ctd_item_in_prompt(self):
        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            query_ai("What CTD items are missing?", s_ctx, r_ctx, "watsonx")

            payload = mock_post.call_args_list[1][1]["json"]
            prompt_text = payload["input"]
            self.assertIn("Process validation", prompt_text)

    def test_api_key_never_in_prompt(self):
        """Credential security: the actual API key value must NOT appear in the
        text-generation payload (the prompt sent to the model)."""
        secret_value = "super-secret-api-key-12345"
        os.environ["WATSONX_API_KEY"] = secret_value

        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            query_ai("Any question.", s_ctx, r_ctx, "watsonx")

            # Only the text-generation payload matters — not the IAM call
            gen_payload = mock_post.call_args_list[1][1]["json"]
            prompt_text = gen_payload.get("input", "")
            self.assertNotIn(secret_value, prompt_text,
                             "The API key value must NOT appear in the model prompt")

        os.environ["WATSONX_API_KEY"] = "key"   # restore to setUp value


class TestFrankfurtConfig(unittest.TestCase):
    """Verify Frankfurt (eu-de) is consistently used as the default region."""

    def test_context_block_built_correctly(self):
        _ss.clear()
        _inject_safety()
        _inject_regulatory()
        s_ctx = build_safety_context()
        r_ctx = build_regulatory_context()
        block = _build_llm_context_block(s_ctx, r_ctx)
        self.assertIn("Atorvastatin", block)
        self.assertIn("36.667", block)
        self.assertIn("Process validation", block)

    def test_default_url_constant_is_frankfurt(self):
        self.assertEqual(_WATSONX_DEFAULT_URL, "https://eu-de.ml.cloud.ibm.com")

    def test_url_override_to_frankfurt_explicitly(self):
        os.environ["WATSONX_API_KEY"]    = "key"
        os.environ["WATSONX_PROJECT_ID"] = "proj"
        os.environ["WATSONX_URL"]        = "https://eu-de.ml.cloud.ibm.com"

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_iam_response(),
                _mock_gen_response("ok"),
            ]
            _call_watsonx("test", "system")
            gen_url = mock_post.call_args_list[1][0][0]
            self.assertIn("eu-de.ml.cloud.ibm.com", gen_url)

        os.environ.pop("WATSONX_API_KEY", None)
        os.environ.pop("WATSONX_PROJECT_ID", None)
        os.environ.pop("WATSONX_URL", None)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = loader.loadTestsFromModule(sys.modules[__name__])
    runner  = unittest.TextTestRunner(verbosity=2)
    result  = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
