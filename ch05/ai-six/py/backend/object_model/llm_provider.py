from abc import ABC, abstractmethod
from typing import Iterator

from backend.object_model.tool import Tool
from backend.object_model.message import AssistantMessage, Message


class LLMProvider(ABC):
    @abstractmethod
    def send(self, messages: list[Message], tool_dict: dict[str, Tool], model: str | None = None) -> AssistantMessage:
        """
        Send a message to the LLM and receive a response.
        :param messages: The list of messages to send.
        :param tool_dict: A dictionary of tools available for the LLM to use.
        :param model: The model to use (optional).
        :return: The assistant message response from the LLM.
        """
        pass

    def stream(self, messages: list[Message], tool_dict: dict[str, Tool], model: str | None = None) -> Iterator[AssistantMessage]:
        """
        Stream a message to the LLM and receive responses as they are generated.
        :param messages: The list of messages to send.
        :param tool_dict: The tools available for the LLM to use.
        :param model: The model to use (optional).
        :return: An iterator of assistant message responses from the LLM.
        """
        # Default implementation just returns the full response
        yield self.send(messages, tool_dict, model)

    @property
    @abstractmethod
    def models(self) -> list[str]:
        """ Get the list of available models."""
        pass

