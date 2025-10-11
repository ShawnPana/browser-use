from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar, overload

import httpx
from openai import (
	APIConnectionError,
	APIError,
	APIStatusError,
	APITimeoutError,
	AsyncOpenAI,
	RateLimitError,
)
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError, ModelRateLimitError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.nvidia.serializer import NVIDIAMessageSerializer
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

T = TypeVar('T', bound=BaseModel)


@dataclass
class ChatNVIDIA(BaseChatModel):
	"""NVIDIA NIM API wrapper (OpenAI-compatible)."""

	model: str = 'nvidia/llama-3.3-nemotron-super-49b-v1.5'

	# Generation parameters
	max_tokens: int | None = 65536
	temperature: float | None = 0.6
	top_p: float | None = 0.95
	frequency_penalty: float | None = 0.0
	presence_penalty: float | None = 0.0
	seed: int | None = None

	# Connection parameters
	api_key: str | None = None
	base_url: str | httpx.URL | None = 'https://integrate.api.nvidia.com/v1'
	timeout: float | httpx.Timeout | None = None
	client_params: dict[str, Any] | None = None

	@property
	def provider(self) -> str:
		return 'nvidia'

	def _client(self) -> AsyncOpenAI:
		return AsyncOpenAI(
			api_key=self.api_key,
			base_url=self.base_url,
			timeout=self.timeout,
			**(self.client_params or {}),
		)

	@property
	def name(self) -> str:
		return self.model

	def _get_usage(self, response) -> ChatInvokeUsage | None:
		"""Extract usage information from response."""
		if hasattr(response, 'usage') and response.usage is not None:
			return ChatInvokeUsage(
				prompt_tokens=response.usage.prompt_tokens,
				completion_tokens=response.usage.completion_tokens,
				total_tokens=response.usage.total_tokens,
				prompt_cached_tokens=None,
				prompt_cache_creation_tokens=None,
				prompt_image_tokens=None,
			)
		return None

	@overload
	async def ainvoke(
		self,
		messages: list[BaseMessage],
		output_format: None = None,
	) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(
		self,
		messages: list[BaseMessage],
		output_format: type[T],
	) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self,
		messages: list[BaseMessage],
		output_format: type[T] | None = None,
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
		"""
		NVIDIA NIM ainvoke supports:
		1. Regular text/multi-turn conversation
		2. JSON Output (response_format)
		"""
		client = self._client()
		nvidia_messages = NVIDIAMessageSerializer.serialize_messages(messages)
		common: dict[str, Any] = {}

		if self.temperature is not None:
			common['temperature'] = self.temperature
		if self.max_tokens is not None:
			common['max_tokens'] = self.max_tokens
		if self.top_p is not None:
			common['top_p'] = self.top_p
		if self.frequency_penalty is not None:
			common['frequency_penalty'] = self.frequency_penalty
		if self.presence_penalty is not None:
			common['presence_penalty'] = self.presence_penalty
		if self.seed is not None:
			common['seed'] = self.seed

		# Regular multi-turn conversation/text output
		if output_format is None:
			try:
				resp = await client.chat.completions.create(  # type: ignore
					model=self.model,
					messages=nvidia_messages,  # type: ignore
					**common,
				)
				usage = self._get_usage(resp)
				return ChatInvokeCompletion(
					completion=resp.choices[0].message.content or '',
					usage=usage,
				)
			except RateLimitError as e:
				raise ModelRateLimitError(str(e), model=self.name) from e
			except (APIError, APIConnectionError, APITimeoutError, APIStatusError) as e:
				raise ModelProviderError(str(e), model=self.name) from e
			except Exception as e:
				raise ModelProviderError(str(e), model=self.name) from e

		# JSON Output path (response_format)
		if output_format is not None and hasattr(output_format, 'model_json_schema'):
			try:
				resp = await client.chat.completions.create(  # type: ignore
					model=self.model,
					messages=nvidia_messages,  # type: ignore
					response_format={'type': 'json_object'},
					**common,
				)
				content = resp.choices[0].message.content
				if not content:
					raise ModelProviderError('Empty JSON content in NVIDIA response', model=self.name)
				parsed = output_format.model_validate_json(content)
				usage = self._get_usage(resp)
				return ChatInvokeCompletion(
					completion=parsed,
					usage=usage,
				)
			except RateLimitError as e:
				raise ModelRateLimitError(str(e), model=self.name) from e
			except (APIError, APIConnectionError, APITimeoutError, APIStatusError) as e:
				raise ModelProviderError(str(e), model=self.name) from e
			except Exception as e:
				raise ModelProviderError(str(e), model=self.name) from e

		raise ModelProviderError('No valid ainvoke execution path for NVIDIA LLM', model=self.name)
