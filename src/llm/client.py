from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from .json_parser import parse_json_strict


# -------------------------
# Env helpers
# -------------------------
def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).strip() in ("1", "true", "True", "yes", "YES")


def _env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_float(key: str, default: str = "30") -> float:
    try:
        return float(os.getenv(key, default).strip() or default)
    except Exception:
        return float(default)


def _safe_float(val: str, default: float) -> float:
    try:
        return float((val or "").strip())
    except Exception:
        return float(default)


# -------------------------
# Client
# -------------------------
class LLMClient:
    """
    Single entry point for LLM calls.

    Hackathon-mode:
    - USE_LLM=0 => never calls external model, returns safe stub outputs
    - USE_LLM=1 => calls endpoint (openai-compatible or custom)

    Supported gateway patterns:
      - OpenAI-compatible chat completions (/v1/chat/completions)
      - Practicus/Vodafone gateway that expects extra auth in payload["metadata"] = {"username": "...", "pwd": "..."}
    """

    def __init__(self, prompts_dir: str = "src/llm/prompts"):
        self.prompts_dir = prompts_dir
        self.use_llm = _env_bool("USE_LLM", "0")

        # Endpoint mode:
        # - openai: OpenAI-compatible chat completions
        # - custom: simple JSON endpoint
        self.mode = _env_str("LLM_MODE", "openai").lower()
        self.timeout_sec = _env_float("LLM_TIMEOUT_SEC", "30")

        # OpenAI-compatible config
        self.base_url = _env_str("LLM_BASE_URL", "").rstrip("/")
        self.api_key = _env_str("LLM_API_KEY", "")
        self.model = _env_str("LLM_MODEL", "")

        # Practicus/Vodafone metadata auth (optional)
        self.md_username = _env_str("LLM_METADATA_USERNAME", "")
        self.md_password = _env_str("LLM_METADATA_PASSWORD", "")

        # SSL verify (enterprise cert/proxy)
        self.verify_ssl = _env_bool("LLM_VERIFY_SSL", "1")

        # Custom endpoint config
        self.endpoint = _env_str("LLM_ENDPOINT", "")
        self.header_name = _env_str("LLM_HEADER_NAME", "Authorization")
        self.header_value = _env_str("LLM_HEADER_VALUE", "")

        # Optional knobs
        self.temperature = _safe_float(_env_str("LLM_TEMPERATURE", "0.2"), 0.2)

        # Some gateways use max_output_tokens; default to OpenAI field "max_tokens"
        self.openai_token_field = _env_str("LLM_OPENAI_TOKEN_FIELD", "max_tokens").strip() or "max_tokens"

    def _load_prompt(self, name: str) -> str:
        path = os.path.join(self.prompts_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # -------------------------
    # Public API
    # -------------------------
    def run_json(
        self,
        prompt_name: str,
        variables: Dict[str, Any],
        max_output_tokens: int = 500,
    ) -> Dict[str, Any]:
        """
        Returns a dict parsed from model output (strict JSON expected).

        Demo-safe:
        - USE_LLM=0 => returns stub dict (prompt-aware)
        - JSON parse fails => returns fallback dict
        """
        prompt_tmpl = self._load_prompt(prompt_name)
        prompt = prompt_tmpl.format(**variables)

        if not self.use_llm:
            return self._stub_json(prompt_name, variables)

        raw = self._call_model(prompt, max_output_tokens=max_output_tokens)

        try:
            return parse_json_strict(raw)
        except Exception:
            # keep wizard alive
            return {
                "value": raw.strip(),
                "confidence": 0.5,
                "needs_clarification": False,
                "followup_question": None,
            }

    def run_text(
        self,
        prompt_name: str,
        variables: Dict[str, Any],
        max_output_tokens: int = 1200,
    ) -> str:
        """
        Returns plain text from model.

        Demo-safe:
        - USE_LLM=0 => deterministic placeholder text
        """
        prompt_tmpl = self._load_prompt(prompt_name)
        prompt = prompt_tmpl.format(**variables)

        if not self.use_llm:
            return self._stub_text(prompt_name, variables)

        return self._call_model(prompt, max_output_tokens=max_output_tokens)

    # -------------------------
    # Stubs (demo mode)
    # -------------------------
    def _stub_json(self, prompt_name: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        # normalize_answer.txt expected output
        if "normalize_answer" in prompt_name:
            user_answer = str(variables.get("user_answer", "")).strip()
            return {
                "value": user_answer,
                "confidence": 0.7,
                "needs_clarification": False,
                "followup_question": None,
            }

        return {
            "value": str(variables.get("user_answer", "")).strip(),
            "confidence": 0.6,
            "needs_clarification": False,
            "followup_question": None,
        }

    def _stub_text(self, prompt_name: str, variables: Dict[str, Any]) -> str:
        if "generate_section" in prompt_name:
            section = variables.get("section_name", "Section")
            content = variables.get("fields_context", "") or variables.get("user_answer", "")
            return f"{section}\n\n{content}".strip()

        return (variables.get("user_answer") or variables.get("fields_context") or "").strip()

    # -------------------------
    # Model call (endpoint)
    # -------------------------
    def _call_model(self, prompt: str, max_output_tokens: int) -> str:
        """
        Must return raw text response.

        Supports:
          - LLM_MODE=openai : OpenAI-compatible chat completions
          - LLM_MODE=custom : LLM_ENDPOINT JSON API

        Any exception here will be caught by flow fallbacks,
        so wizard won't crash.
        """
        mode = (self.mode or "openai").lower()
        if mode == "custom":
            return self._call_custom(prompt, max_output_tokens)
        return self._call_openai_compatible(prompt, max_output_tokens)

    def _call_custom(self, prompt: str, max_output_tokens: int) -> str:
        endpoint = self.endpoint
        if not endpoint:
            raise RuntimeError("LLM_ENDPOINT is required when LLM_MODE=custom")

        headers = {"Content-Type": "application/json"}
        if self.header_value:
            headers[self.header_name] = self.header_value

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model": self.model or None,
            "max_output_tokens": int(max_output_tokens),
            "temperature": float(self.temperature),
        }

        # Optional metadata auth (if custom gateway uses it too)
        md = self._build_metadata()
        if md:
            payload["metadata"] = md

        r = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout_sec,
            verify=self.verify_ssl,
        )
        if not r.ok:
            raise RuntimeError(f"Custom LLM HTTP {r.status_code}: {r.text[:500]}")

        try:
            data = r.json()
        except Exception:
            return r.text

        #print("Custom LLM response data:", data)
        # Common shapes
        if isinstance(data, dict):
            if isinstance(data.get("text"), str):
                return data["text"]
            if isinstance(data.get("output"), str):
                return data["output"]

            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                ch0 = choices[0]
                if isinstance(ch0, dict):
                    if isinstance(ch0.get("text"), str):
                        return ch0["text"]
                    msg = ch0.get("message")
                    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                        return msg["content"]

        return r.text

    def _resolve_openai_url(self) -> str:
        """
        Accepts:
          - LLM_BASE_URL = https://host
          - LLM_BASE_URL = https://host/.../latest
          - LLM_BASE_URL = https://host/.../latest/v1
          - LLM_BASE_URL = https://host/.../latest/v1/chat/completions
        Returns final url ending with /v1/chat/completions
        """
        base = (self.base_url or "").rstrip("/")
        if not base:
            return ""

        if base.endswith("/v1/chat/completions"):
            return base
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def _build_metadata(self) -> Optional[Dict[str, str]]:
        """
        Practicus/Vodafone gateway wants:
          metadata: { "username": "...", "pwd": "..." }
        Only include if both provided.
        """
        u = (self.md_username or "").strip()
        p = (self.md_password or "").strip()
        if not u or not p:
            return None
        return {"username": u, "pwd": p}

    def _call_openai_compatible(self, prompt: str, max_output_tokens: int) -> str:
        if not self.base_url:
            raise RuntimeError("LLM_BASE_URL is required when LLM_MODE=openai")
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is required when LLM_MODE=openai")
        if not self.model:
            raise RuntimeError("LLM_MODEL is required when LLM_MODE=openai")

        url = self._resolve_openai_url()
        if not url:
            raise RuntimeError("Failed to resolve OpenAI-compatible URL from LLM_BASE_URL")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Follow the prompt rules strictly. Return only the requested output.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": float(self.temperature),
        }

        # Token field differs across gateways; default "max_tokens"
        payload[self.openai_token_field] = int(max_output_tokens)

        # ✅ Practicus/Vodafone metadata auth (optional)
        md = self._build_metadata()
        if md:
            payload["metadata"] = md

        #print("AI request payload:", payload)

        r = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout_sec,
            verify=self.verify_ssl,
        )

        if not r.ok:
            raise RuntimeError(f"OpenAI-compatible HTTP {r.status_code}: {r.text[:500]}")

        try:
            data = r.json()
            #print("AI response data:", data)
        except Exception:
            return r.text

        # OpenAI-like response
        try:
            return str(data["choices"][0]["message"]["content"])
        except Exception:
            try:
                return str(data["choices"][0]["text"])
            except Exception:
                return r.text
