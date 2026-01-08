from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .json_parser import parse_json_strict


class LLMClient:
    """
    Single entry point for LLM calls.
    Wire this to your existing AI infrastructure (OpenAI/Azure/local/etc.).
    """

    def __init__(self, prompts_dir: str = "src/llm/prompts"):
        self.prompts_dir = prompts_dir

    def _load_prompt(self, name: str) -> str:
        path = os.path.join(self.prompts_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def run_json(
        self,
        prompt_name: str,
        variables: Dict[str, Any],
        max_output_tokens: int = 500,
    ) -> Dict[str, Any]:
        """
        Returns a dict parsed from model output (strict JSON expected).
        """
        prompt_tmpl = self._load_prompt(prompt_name)
        prompt = prompt_tmpl.format(**variables)

        raw = self._call_model(prompt, max_output_tokens=max_output_tokens)
        return parse_json_strict(raw)

    def run_text(
        self,
        prompt_name: str,
        variables: Dict[str, Any],
        max_output_tokens: int = 1200,
    ) -> str:
        prompt_tmpl = self._load_prompt(prompt_name)
        prompt = prompt_tmpl.format(**variables)
        return self._call_model(prompt, max_output_tokens=max_output_tokens)

    # ---- Implement this with your AI stack ----
    def _call_model(self, prompt: str, max_output_tokens: int) -> str:
        """
        Implement using your existing LLM stack.
        Must return raw text response.
        """
        raise NotImplementedError(
            "Wire _call_model() to your existing AI infrastructure."
        )
