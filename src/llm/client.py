from __future__ import annotations

import os
from typing import Any, Dict

from .json_parser import parse_json_strict


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).strip() in ("1", "true", "True", "yes", "YES")


class LLMClient:
    """
    Single entry point for LLM calls.

    Hackathon-mode:
    - USE_LLM=0 => never calls external model, returns safe stub outputs
    - USE_LLM=1 => calls _call_model(), teammate wires endpoint
    """

    def __init__(self, prompts_dir: str = "src/llm/prompts"):
        self.prompts_dir = prompts_dir
        self.use_llm = _env_bool("USE_LLM", "0")

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

        # strict parse; if it fails, fallback to best-effort
        try:
            return parse_json_strict(raw)
        except Exception:
            # Fallback: keep demo alive
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
        """
        Prompt-aware stub. Keeps pipeline running without LLM.
        """
        # normalize_answer.txt expected output: {"value": "...", "confidence": ...}
        if "normalize_answer" in prompt_name:
            user_answer = str(variables.get("user_answer", "")).strip()
            return {
                "value": user_answer,
                "confidence": 0.7,
                "needs_clarification": False,
                "followup_question": None,
            }

        # update_summary.txt or other json prompts (if any)
        return {
            "value": str(variables.get("user_answer", "")).strip(),
            "confidence": 0.6,
            "needs_clarification": False,
            "followup_question": None,
        }

    def _stub_text(self, prompt_name: str, variables: Dict[str, Any]) -> str:
        """
        Text stub for preview generation etc.
        """
        # generate_section.txt -> return simple formatted output
        if "generate_section" in prompt_name:
            section = variables.get("section_name", "Section")
            content = variables.get("fields_context", "") or variables.get("user_answer", "")
            return f"{section}\n\n{content}".strip()

        # generic
        return (variables.get("user_answer") or variables.get("fields_context") or "").strip()

    # -------------------------
    # Implement this with AI stack
    # -------------------------
    def _call_model(self, prompt: str, max_output_tokens: int) -> str:
        """
        Teammate wires endpoint here.
        Must return raw text response.
        """
        raise NotImplementedError("Wire _call_model() to your existing AI infrastructure.")
