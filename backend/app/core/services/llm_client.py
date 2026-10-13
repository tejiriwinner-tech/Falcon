"""
Falcon Multi-Provider LLM Client
Direct, zero-heavy-dependency client using httpx to interface with
Google Gemini, OpenAI, and Anthropic APIs.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config.settings import settings
from app.schemas.copilot import ActionChip, ChatMessage

logger = logging.getLogger("falcon.llm_client")


class FalconLLMClient:
    """Dispatches reasoning queries to configured LLM providers with automatic fallback."""

    def __init__(self) -> None:
        self.timeout = 8.0  # Max 8 seconds before falling back to local expert engine

    def is_available(self) -> bool:
        """Returns True if any valid LLM API key is configured."""
        return bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)

    def get_active_provider_name(self) -> str:
        """Returns human-readable name of the primary active LLM provider."""
        if settings.GEMINI_API_KEY:
            return f"Gemini ({settings.COPILOT_MODEL_NAME})"
        if settings.OPENAI_API_KEY:
            return "OpenAI (GPT-4o)"
        if settings.ANTHROPIC_API_KEY:
            return "Anthropic (Claude 3.5)"
        return "Falcon Institutional Engine"

    def generate(
        self,
        system_prompt: str,
        user_query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        context_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[ActionChip], str]:
        """
        Executes query against active LLM provider.
        Returns (response_text, action_chips, provider_name).
        Raises Exception if all providers fail.
        """
        # Determine provider priority
        if settings.GEMINI_API_KEY:
            return self._call_gemini(system_prompt, user_query, conversation_history, context_snapshot)
        elif settings.OPENAI_API_KEY:
            return self._call_openai(system_prompt, user_query, conversation_history, context_snapshot)
        elif settings.ANTHROPIC_API_KEY:
            return self._call_anthropic(system_prompt, user_query, conversation_history, context_snapshot)
        else:
            raise ValueError("No LLM API keys configured.")

    def _call_gemini(
        self,
        system_prompt: str,
        user_query: str,
        conversation_history: Optional[List[ChatMessage]],
        context_snapshot: Optional[Dict[str, Any]],
    ) -> Tuple[str, List[ActionChip], str]:
        """Invokes Google Gemini REST API with header authentication and model fallback."""
        api_key = settings.GEMINI_API_KEY
        candidate_models = [
            settings.COPILOT_MODEL_NAME or "gemini-3.5-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
        # De-duplicate while preserving order
        unique_models = list(dict.fromkeys(candidate_models))

        # Construct payload with context snapshot
        user_prompt_with_context = user_query
        if context_snapshot:
            compact_ctx = json.dumps(context_snapshot, separators=(",", ":"), default=str)
            user_prompt_with_context = (
                f"[LIVE FALCON TELEMETRY SNAPSHOT]\n{compact_ctx}\n\n"
                f"[TRADER QUERY]\n{user_query}"
            )

        contents = []
        if conversation_history:
            for msg in conversation_history[-6:]:  # Keep recent 6 turns for context
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        contents.append({"role": "user", "parts": [{"text": user_prompt_with_context}]})

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": settings.COPILOT_TEMPERATURE,
                "maxOutputTokens": settings.COPILOT_MAX_TOKENS,
            },
        }

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        last_error = None
        for model in unique_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            clean_text, action_chips = self._extract_actions(raw_text)
                            return clean_text, action_chips, f"gemini/{model}"
                    logger.warning(f"Gemini {model} returned status {resp.status_code}: {resp.text[:150]}")
                    last_error = f"Gemini {model} error {resp.status_code}"
            except Exception as ex:
                logger.warning(f"Gemini {model} request exception: {ex}")
                last_error = str(ex)

        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    def _call_openai(
        self,
        system_prompt: str,
        user_query: str,
        conversation_history: Optional[List[ChatMessage]],
        context_snapshot: Optional[Dict[str, Any]],
    ) -> Tuple[str, List[ActionChip], str]:
        """Invokes OpenAI Chat Completions API."""
        api_key = settings.OPENAI_API_KEY
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o-mini"

        user_content = user_query
        if context_snapshot:
            compact_ctx = json.dumps(context_snapshot, separators=(",", ":"), default=str)
            user_content = f"[LIVE TELEMETRY SNAPSHOT]\n{compact_ctx}\n\n[TRADER QUERY]\n{user_query}"

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_content})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.COPILOT_TEMPERATURE,
            "max_tokens": settings.COPILOT_MAX_TOKENS,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API Error {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            clean_text, action_chips = self._extract_actions(raw_text)
            return clean_text, action_chips, f"openai/{model}"

    def _call_anthropic(
        self,
        system_prompt: str,
        user_query: str,
        conversation_history: Optional[List[ChatMessage]],
        context_snapshot: Optional[Dict[str, Any]],
    ) -> Tuple[str, List[ActionChip], str]:
        """Invokes Anthropic Messages API."""
        api_key = settings.ANTHROPIC_API_KEY
        url = "https://api.anthropic.com/v1/messages"
        model = "claude-3-5-sonnet-20241022"

        user_content = user_query
        if context_snapshot:
            compact_ctx = json.dumps(context_snapshot, separators=(",", ":"), default=str)
            user_content = f"[LIVE TELEMETRY SNAPSHOT]\n{compact_ctx}\n\n[TRADER QUERY]\n{user_query}"

        messages = []
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_content})

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": settings.COPILOT_MAX_TOKENS,
            "temperature": settings.COPILOT_TEMPERATURE,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Anthropic API Error {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            raw_text = data["content"][0]["text"]
            clean_text, action_chips = self._extract_actions(raw_text)
            return clean_text, action_chips, f"anthropic/{model}"

    def _extract_actions(self, text: str) -> Tuple[str, List[ActionChip]]:
        """
        Parses json:actions code block from the LLM output,
        converts them to ActionChip models, and removes the block from prose.
        """
        actions: List[ActionChip] = []
        pattern = r"```json:actions\s*(\[[\s\S]*?\])\s*```"
        match = re.search(pattern, text)
        if match:
            raw_json = match.group(1)
            try:
                items = json.loads(raw_json)
                for item in items:
                    if isinstance(item, dict) and "label" in item and "action" in item:
                        actions.append(ActionChip(
                            label=item["label"],
                            action=item["action"],
                            payload=item.get("payload", {})
                        ))
                # Strip json:actions block from displayed text
                text = re.sub(pattern, "", text).strip()
            except Exception as ex:
                logger.debug(f"Action chip JSON parse error: {ex}")

        # If no explicit action chips returned, synthesize default helpful ones
        if not actions:
            actions = [
                ActionChip(label="Audit Risk Limits", action="AUDIT_RISK", payload={}),
                ActionChip(label="Check Calendar", action="VIEW_CALENDAR", payload={}),
            ]

        return text, actions


llm_client = FalconLLMClient()
