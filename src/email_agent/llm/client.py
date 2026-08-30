"""Thin wrapper around the Anthropic SDK.

This is the only module in the application that imports `anthropic`. Every other
module talks to `ClaudeClient.generate(prompt) -> str`, so swapping providers or
mocking Claude in tests never touches business logic.
"""

from __future__ import annotations

import anthropic

from email_agent.config import Config


class ClaudeClientError(Exception):
    """Raised when the Claude API cannot be reached or returns an error."""


class ClaudeClient:
    def __init__(self, config: Config) -> None:
        if not config.anthropic_api_key:
            raise ClaudeClientError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self._model = config.claude_model
        self._max_tokens = config.claude_max_tokens

        # Some API keys are "identity-linked" (issued via SSO under an
        # organization with multiple workspaces) and require an explicit
        # anthropic-workspace-id header on every request; a standard
        # personal API key does not need this, so it's optional.
        default_headers = {}
        if config.anthropic_workspace_id:
            default_headers["anthropic-workspace-id"] = config.anthropic_workspace_id

        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key, default_headers=default_headers)

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Send a single-turn prompt to Claude and return the text response."""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APITimeoutError as exc:
            raise ClaudeClientError("Claude API request timed out.") from exc
        except anthropic.RateLimitError as exc:
            raise ClaudeClientError("Claude API rate limit exceeded.") from exc
        except anthropic.APIStatusError as exc:
            raise ClaudeClientError(f"Claude API returned an error: {exc.status_code} {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ClaudeClientError("Could not connect to the Claude API.") from exc
        except anthropic.AnthropicError as exc:
            raise ClaudeClientError(f"Claude API error: {exc}") from exc

        text_blocks = [block.text for block in response.content if block.type == "text"]
        if not text_blocks:
            raise ClaudeClientError("Claude returned an empty response.")
        return "".join(text_blocks)
