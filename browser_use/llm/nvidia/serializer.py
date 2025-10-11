"""Message serializer for NVIDIA NIM API (OpenAI-compatible)."""

from openai.types.chat import ChatCompletionMessageParam

from browser_use.llm.messages import BaseMessage
from browser_use.llm.openai.serializer import OpenAIMessageSerializer


class NVIDIAMessageSerializer:
	"""Serializer for NVIDIA NIM API messages - reuses OpenAI serialization."""

	@staticmethod
	def serialize(message: BaseMessage) -> ChatCompletionMessageParam:
		"""Serialize a message to NVIDIA NIM format (OpenAI-compatible)."""
		return OpenAIMessageSerializer.serialize(message)

	@staticmethod
	def serialize_messages(messages: list[BaseMessage]) -> list[ChatCompletionMessageParam]:
		"""Serialize a list of messages to NVIDIA NIM format."""
		return OpenAIMessageSerializer.serialize_messages(messages)
