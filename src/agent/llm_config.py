"""
LiteLLM Configuration Module

This module provides a unified interface to multiple LLM providers using LiteLLM.
LiteLLM supports 100+ LLM providers with a consistent OpenAI-compatible API.

Supported providers:
- Anthropic (Claude models)
- OpenAI (GPT models)
- Azure OpenAI
- Google (Gemini models)
- AWS Bedrock
- Cohere
- Replicate
- And many more...

Environment variables required:
- LLM_PROVIDER: Provider name (e.g., "anthropic", "openai", "azure")
- LLM_MODEL: Model identifier (e.g., "claude-sonnet-4-20250514", "gpt-4", "gemini-pro")
- LLM_API_KEY: API key for the provider (or provider-specific key like ANTHROPIC_API_KEY)
- LLM_BASE_URL: (Optional) Custom base URL for self-hosted or proxy endpoints
- LLM_MAX_TOKENS: (Optional) Max tokens for responses (default: 4096)
- LLM_TEMPERATURE: (Optional) Temperature for responses (default: 0.0 for deterministic)
"""

from typing import Dict, List, Optional, Any
from pydantic import Field
from pydantic_settings import BaseSettings
import litellm
from litellm import completion, acompletion


class LLMSettings(BaseSettings):
    """LLM configuration settings"""

    # Provider and model
    llm_provider: str = Field(default="anthropic", description="LLM provider name")
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model identifier"
    )

    # API credentials
    llm_api_key: Optional[str] = Field(default=None, description="API key for LLM provider")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    azure_api_key: Optional[str] = Field(default=None, description="Azure API key")
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")

    # Optional configuration
    llm_base_url: Optional[str] = Field(default=None, description="Custom base URL")
    llm_max_tokens: int = Field(default=4096, description="Max tokens for completion")
    llm_temperature: float = Field(default=0.0, description="Temperature (0.0 = deterministic)")
    llm_timeout: int = Field(default=60, description="Request timeout in seconds")

    # LiteLLM specific settings
    litellm_log_level: str = Field(default="ERROR", description="LiteLLM log level")
    litellm_drop_params: bool = Field(
        default=True,
        description="Drop unsupported params for each provider"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class LLMClient:
    """
    Unified LLM client using LiteLLM.

    Supports function calling, streaming, and async operations.
    """

    def __init__(self, settings: Optional[LLMSettings] = None):
        """
        Initialize LLM client.

        Args:
            settings: LLM settings (defaults to loading from environment)
        """
        self.settings = settings or LLMSettings()

        # Configure LiteLLM
        litellm.drop_params = self.settings.litellm_drop_params
        litellm.set_verbose = self.settings.litellm_log_level == "DEBUG"

        # Set API key based on provider
        self._configure_api_key()

        # Build model string (provider/model format for LiteLLM)
        self.model = self._build_model_string()

    def _configure_api_key(self):
        """Set API key for the selected provider"""
        provider = self.settings.llm_provider.lower()

        # Priority: provider-specific key > generic llm_api_key
        if provider == "anthropic":
            key = self.settings.anthropic_api_key or self.settings.llm_api_key
            if key:
                litellm.api_key = key
        elif provider == "openai":
            key = self.settings.openai_api_key or self.settings.llm_api_key
            if key:
                litellm.openai_key = key
        elif provider == "azure":
            key = self.settings.azure_api_key or self.settings.llm_api_key
            if key:
                litellm.azure_key = key
        elif provider == "gemini" or provider == "google":
            key = self.settings.gemini_api_key or self.settings.llm_api_key
            if key:
                litellm.gemini_api_key = key
        else:
            # Generic fallback
            if self.settings.llm_api_key:
                litellm.api_key = self.settings.llm_api_key

    def _build_model_string(self) -> str:
        """
        Build LiteLLM model string.

        Format: "provider/model" or just "model" for OpenAI-compatible APIs

        Examples:
        - "anthropic/claude-sonnet-4-20250514"
        - "gpt-4" (OpenAI default)
        - "azure/gpt-4"
        - "gemini/gemini-pro"
        """
        provider = self.settings.llm_provider.lower()
        model = self.settings.llm_model

        # For Anthropic, use provider prefix
        if provider == "anthropic":
            # LiteLLM requires "anthropic/" prefix for Claude models
            if not model.startswith("anthropic/"):
                return f"anthropic/{model}"
            return model

        # For other providers, use provider/model format if needed
        if provider in ["azure", "bedrock", "vertex_ai", "palm"]:
            return f"{provider}/{model}"

        # OpenAI and OpenAI-compatible APIs use model name directly
        return model

    def complete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Any:
        """
        Generate completion using LiteLLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool/function definitions
            tool_choice: Optional tool choice strategy ("auto", "required", or specific tool)
            stream: Whether to stream the response
            **kwargs: Additional parameters to pass to litellm.completion()

        Returns:
            LiteLLM completion response or stream

        Example:
            >>> client = LLMClient()
            >>> response = client.complete(
            ...     messages=[{"role": "user", "content": "Hello!"}]
            ... )
            >>> print(response.choices[0].message.content)
        """
        # Build request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.settings.llm_max_tokens),
            "temperature": kwargs.get("temperature", self.settings.llm_temperature),
            "timeout": kwargs.get("timeout", self.settings.llm_timeout),
            "stream": stream,
        }

        # Add base URL if configured
        if self.settings.llm_base_url:
            params["api_base"] = self.settings.llm_base_url

        # Add tools if provided
        if tools:
            params["tools"] = tools
            if tool_choice:
                params["tool_choice"] = tool_choice

        # Merge additional kwargs
        params.update({k: v for k, v in kwargs.items() if k not in params})

        # Call LiteLLM
        return completion(**params)

    async def acomplete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Any:
        """
        Async version of complete().

        Same parameters as complete() but returns awaitable.
        """
        # Build request parameters (same as complete)
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.settings.llm_max_tokens),
            "temperature": kwargs.get("temperature", self.settings.llm_temperature),
            "timeout": kwargs.get("timeout", self.settings.llm_timeout),
            "stream": stream,
        }

        if self.settings.llm_base_url:
            params["api_base"] = self.settings.llm_base_url

        if tools:
            params["tools"] = tools
            if tool_choice:
                params["tool_choice"] = tool_choice

        params.update({k: v for k, v in kwargs.items() if k not in params})

        # Call LiteLLM async
        return await acompletion(**params)

    def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Count tokens in messages using LiteLLM's token counter.

        Args:
            messages: List of message dicts

        Returns:
            Estimated token count
        """
        try:
            return litellm.token_counter(model=self.model, messages=messages)
        except Exception:
            # Fallback: rough estimate (4 chars = 1 token)
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            return total_chars // 4


# Singleton instance for easy import
_default_client: Optional[LLMClient] = None


def get_llm_client(settings: Optional[LLMSettings] = None) -> LLMClient:
    """
    Get or create the default LLM client.

    Args:
        settings: Optional settings (creates new client if provided)

    Returns:
        LLM client instance
    """
    global _default_client

    if settings is not None:
        return LLMClient(settings)

    if _default_client is None:
        _default_client = LLMClient()

    return _default_client


# Example usage
if __name__ == "__main__":
    # Example 1: Using Anthropic Claude
    print("Example 1: Anthropic Claude")
    client = LLMClient()
    response = client.complete(
        messages=[
            {"role": "user", "content": "What is the capital of France?"}
        ]
    )
    print(response.choices[0].message.content)

    # Example 2: With tools/function calling
    print("\nExample 2: Function calling")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "Get current stock price for a ticker",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL')"
                        }
                    },
                    "required": ["ticker"]
                }
            }
        }
    ]

    response = client.complete(
        messages=[
            {"role": "user", "content": "What's the current price of Apple stock?"}
        ],
        tools=tools,
        tool_choice="auto"
    )
    print(response.choices[0].message)
