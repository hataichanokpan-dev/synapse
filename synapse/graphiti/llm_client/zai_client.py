"""
Custom LLM client for Z.ai API (Anthropic-compatible endpoint).

Z.ai wraps GLM models with an Anthropic-compatible API at /v1/messages.
This client uses that format instead of OpenAI's /chat/completions format.
"""

import json
import logging
import typing
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel

from graphiti_core.llm_client.client import LLMClient, get_extraction_language_instruction
from graphiti_core.llm_client.config import DEFAULT_MAX_TOKENS, LLMConfig, ModelSize
from graphiti_core.llm_client.errors import RateLimitError
from graphiti_core.prompts.models import Message

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"  # Z.ai maps this to GLM-4.7


class ZaiClient(LLMClient):
    """
    LLM client for Z.ai API (Anthropic-compatible endpoint).

    Uses Anthropic Messages API format:
    - Endpoint: /v1/messages
    - Headers: x-api-key, anthropic-version
    - Body: model, max_tokens, messages
    """

    MAX_RETRIES: ClassVar[int] = 2

    def __init__(
        self,
        config: LLMConfig | None = None,
        cache: bool = False,
        max_tokens: int = 4096,
    ):
        """
        Initialize Z.ai client.

        Args:
            config: LLM configuration with api_key and base_url
            cache: Whether to enable caching (not implemented)
            max_tokens: Maximum tokens for responses
        """
        if cache:
            raise NotImplementedError("Caching is not implemented for Z.ai client")

        if config is None:
            config = LLMConfig()

        super().__init__(config, cache)

        self.max_tokens = max_tokens
        self.api_key = config.api_key
        self.base_url = (config.base_url or "https://api.z.ai/api/anthropic").rstrip("/")

    def _get_provider_type(self) -> str:
        """Get provider type for tracing."""
        return "zai"

    def _strip_markdown_code_block(self, text: str) -> str:
        """
        Strip markdown code blocks from LLM response.

        Z.ai often wraps JSON in ```json ... ``` blocks.
        """
        import re

        text = text.strip()

        # Match ```json ... ``` or ``` ... ``` patterns
        pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
        match = re.match(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        # Also handle cases where code block is not at the very start/end
        if text.startswith("```"):
            # Find the end of the opening code fence
            first_newline = text.find("\n")
            if first_newline != -1:
                # Find the closing fence
                last_fence = text.rfind("```")
                if last_fence > first_newline:
                    return text[first_newline + 1 : last_fence].strip()

        return text

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        """
        Generate response from Z.ai API using Anthropic format.

        Args:
            messages: List of Message objects
            response_model: Optional Pydantic model for structured output
            max_tokens: Maximum tokens to generate
            model_size: Model size (not used, kept for interface compatibility)

        Returns:
            Parsed JSON response as dict
        """
        # Convert Graphiti messages to Anthropic format
        anthropic_messages = []
        system_content = None

        for m in messages:
            cleaned_content = self._clean_input(m.content)
            if m.role == "system":
                # Anthropic uses separate system parameter
                system_content = cleaned_content
            elif m.role == "user":
                anthropic_messages.append({"role": "user", "content": cleaned_content})
            elif m.role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": cleaned_content})

        # Add JSON format instruction if response_model provided
        if response_model is not None:
            schema = response_model.model_json_schema()
            format_instruction = f"\n\nRespond with a JSON object in the following format:\n\n{json.dumps(schema)}"
            if anthropic_messages:
                anthropic_messages[-1]["content"] += format_instruction
            elif system_content:
                system_content += format_instruction

        # Build request body
        request_body = {
            "model": self.model or DEFAULT_MODEL,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": anthropic_messages,
        }
        if system_content:
            request_body["system"] = system_content

        # Make API request
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=request_body, headers=headers)

            if response.status_code == 429:
                raise RateLimitError("Z.ai rate limit exceeded")

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Z.ai API error: {response.status_code} - {error_text}")
                raise Exception(f"Z.ai API error: {response.status_code} - {error_text}")

            data = response.json()

        # Parse response
        # Anthropic format: {"content": [{"type": "text", "text": "..."}], ...}
        try:
            content_blocks = data.get("content", [])
            if not content_blocks:
                raise ValueError("Empty response from Z.ai")

            text_content = None
            for block in content_blocks:
                if block.get("type") == "text":
                    text_content = block.get("text", "")
                    break

            if text_content is None:
                raise ValueError("No text content in Z.ai response")

            # Strip markdown code blocks if present
            text_content = self._strip_markdown_code_block(text_content)

            # Try to parse as JSON
            try:
                return json.loads(text_content)
            except json.JSONDecodeError:
                # If not valid JSON, wrap in a dict
                logger.warning(f"Z.ai returned non-JSON response, wrapping: {text_content[:100]}")
                return {"response": text_content}

        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse Z.ai response: {e}")
            raise ValueError(f"Invalid Z.ai response format: {e}")

    async def generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        model_size: ModelSize = ModelSize.medium,
        group_id: str | None = None,
        prompt_name: str | None = None,
    ) -> dict[str, typing.Any]:
        """
        Generate response with retry logic.

        Args:
            messages: List of Message objects
            response_model: Optional Pydantic model for structured output
            max_tokens: Maximum tokens to generate
            model_size: Model size
            group_id: Group ID for context
            prompt_name: Prompt name for tracing

        Returns:
            Parsed JSON response as dict
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        # Add multilingual extraction instructions
        messages[0].content += get_extraction_language_instruction(group_id)

        # Wrap in tracing span
        with self.tracer.start_span("llm.generate") as span:
            attributes = {
                "llm.provider": "zai",
                "model.size": model_size.value,
                "max_tokens": max_tokens,
            }
            if prompt_name:
                attributes["prompt.name"] = prompt_name
            span.add_attributes(attributes)

            retry_count = 0
            last_error = None

            while retry_count <= self.MAX_RETRIES:
                try:
                    response = await self._generate_response(
                        messages, response_model, max_tokens=max_tokens, model_size=model_size
                    )
                    return response
                except RateLimitError:
                    span.set_status("error", "Rate limit exceeded")
                    raise
                except httpx.HTTPStatusError as e:
                    if 500 <= e.response.status_code < 600:
                        # Retry on server errors
                        last_error = e
                        retry_count += 1
                        logger.warning(f"Retrying after server error (attempt {retry_count}/{self.MAX_RETRIES})")
                        continue
                    span.set_status("error", str(e))
                    raise
                except Exception as e:
                    last_error = e

                    if retry_count >= self.MAX_RETRIES:
                        logger.error(f"Max retries ({self.MAX_RETRIES}) exceeded. Last error: {e}")
                        span.set_status("error", str(e))
                        span.record_exception(e)
                        raise

                    retry_count += 1

                    # Add error context for retry
                    error_context = (
                        f"The previous response attempt was invalid. "
                        f"Error type: {e.__class__.__name__}. "
                        f"Error details: {str(e)}. "
                        f"Please try again with a valid JSON response."
                    )
                    error_message = Message(role="user", content=error_context)
                    messages.append(error_message)
                    logger.warning(f"Retrying after error (attempt {retry_count}/{self.MAX_RETRIES}): {e}")

            span.set_status("error", str(last_error))
            raise last_error or Exception("Max retries exceeded")
