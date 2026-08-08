"""
LLM Router for wiki generation and rename suggestions (DEC-12, DEC-13, DEC-16).

Routes requests to either Cloud (Anthropic) or Local (Ollama) based on App_Config.llm_mode.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger("CorpBrain.LLMRouter")


class LLMRouter:
    """
    Routes LLM requests to Cloud (Option A) or Local (Option B).

    DEC-12: Cloud is Anthropic only, model is App_Config.llm_cloud_model.
    DEC-13: Local is Ollama, model is App_Config.local_generation_model.
    DEC-16: Never auto-switch engines. A failure stays a failure.
    """

    def __init__(self, db_mgr, network_guard=None):
        from src.backend.config_manager import ConfigManager
        self.db_mgr = db_mgr
        self.config_mgr = ConfigManager(db_mgr)

        if network_guard is None:
            from src.backend.network_guard import NetworkGuard
            network_guard = NetworkGuard
        self.network_guard = network_guard

    def generate(self, prompt: str, max_tokens: int = 2000) -> Dict[str, Any]:
        """
        Generate text from LLM.

        Args:
            prompt: The input prompt
            max_tokens: Maximum response tokens

        Returns:
            {
                "content": str,
                "usage": {"input_tokens": int, "output_tokens": int},
                "cost_usd": float
            }

        Raises:
            Exception: On LLM failure (caller should use LLMResilienceService for retries)
        """
        mode = self.config_mgr.get("llm_mode", "Option A")

        if mode == "Option A":
            return self._generate_cloud(prompt, max_tokens)
        else:
            return self._generate_local(prompt, max_tokens)

    def _generate_cloud(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """
        Call Anthropic API (DEC-12).
        """
        import anthropic

        # DEC-12: decrypt only in memory, immediately before the call, then discard.
        # Delegated to ConfigManager so DPAPI lives in exactly one place — this method used to
        # carry a second, independent ctypes implementation that had drifted from
        # utils/security.py (different DATA_BLOB field type, different flags) and had no
        # non-Windows guard, so merely reaching it on a dev host raised AttributeError.
        api_key = self.config_mgr.get_api_key()
        if not api_key:
            raise ValueError("API_KEY_NOT_CONFIGURED")

        model = self.config_mgr.get("llm_cloud_model", "claude-sonnet-4")
        float(self.config_mgr.get("llm_timeout_connect", "10"))
        timeout_read = float(self.config_mgr.get("llm_timeout_read", "120"))

        # DEC-15: Egress validation
        self.network_guard.validate_egress("llm_cloud", "https://api.anthropic.com")

        client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout_read,
        )

        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text if response.content else ""
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

            # Calculate cost (DEC-16: from actual usage, not estimates)
            cost_input_per_mtok = float(self.config_mgr.get("cloud_price_input_per_mtok", "3.0"))
            cost_output_per_mtok = float(self.config_mgr.get("cloud_price_output_per_mtok", "15.0"))

            cost_usd = (
                (usage["input_tokens"] / 1_000_000) * cost_input_per_mtok +
                (usage["output_tokens"] / 1_000_000) * cost_output_per_mtok
            )

            return {
                "content": content,
                "usage": usage,
                "cost_usd": cost_usd,
            }

        except anthropic.APIStatusError as e:
            # DEC-16: 401/400 are non-transient, 429/5xx are transient
            if e.status_code in (401, 400):
                logger.error(f"[LLMRouter] Non-transient Anthropic error: {e.status_code}")
            raise

    def _generate_local(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """
        Call Ollama local LLM (DEC-13).
        """
        model = self.config_mgr.get("local_generation_model", "qwen2.5:7b-instruct")
        timeout = float(self.config_mgr.get("llm_timeout_read", "120"))

        # DEC-15: Local only
        url = "http://127.0.0.1:11434/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            }
        }

        try:
            response = self.network_guard.post_json(
                purpose="llm_local",
                url=url,
                payload=payload,
                timeout=timeout
            )

            if not response or "response" not in response:
                raise ValueError("Empty or invalid Ollama response")

            content = response["response"]

            # Ollama doesn't return token counts in all versions, estimate if missing
            input_tokens = response.get("prompt_eval_count", len(prompt) // 4)
            output_tokens = response.get("eval_count", len(content) // 4)

            return {
                "content": content,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
                "cost_usd": 0.0,  # Local has no cost (DEC-16)
            }

        except Exception as e:
            logger.error(f"[LLMRouter] Ollama error: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        Check if the current LLM engine is available.

        Returns:
            {"status_ok": bool, "error_code": str | None}
        """
        mode = self.config_mgr.get("llm_mode", "Option A")

        if mode == "Option A":
            api_key_configured = self.config_mgr.is_api_key_configured()
            if not api_key_configured:
                return {"status_ok": False, "error_code": "API_KEY_NOT_CONFIGURED"}

            # Simple validation check
            try:
                self.network_guard.validate_egress("llm_cloud", "https://api.anthropic.com")
                return {"status_ok": True, "error_code": None}
            except Exception:
                return {"status_ok": False, "error_code": "EGRESS_BLOCKED"}

        else:
            # Check Ollama daemon
            try:
                tags = self.network_guard.get_json(
                    "llm_local",
                    "http://127.0.0.1:11434/api/tags",
                    timeout=5
                )

                if tags is None:
                    return {"status_ok": False, "error_code": "LLM_UNAVAILABLE"}

                model = self.config_mgr.get("local_generation_model", "qwen2.5:7b-instruct")
                installed_models = [m.get("name", "") for m in tags.get("models", [])]
                model_ready = any(model in m for m in installed_models)

                if not model_ready:
                    return {"status_ok": False, "error_code": "LLM_PROVISION_REQUIRED"}

                return {"status_ok": True, "error_code": None}

            except Exception:
                return {"status_ok": False, "error_code": "LLM_UNAVAILABLE"}
