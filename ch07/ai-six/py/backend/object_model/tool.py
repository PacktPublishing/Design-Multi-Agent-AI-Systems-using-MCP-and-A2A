from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import NamedTuple

class Parameter(NamedTuple):
    name: str
    type: str
    description: str

@dataclass(slots=True)
class Tool(ABC):
    name: str
    description: str
    parameters: list[Parameter]
    required: set[str]

    def configure(self, config: dict) -> None:
        """Optional: configure the tool with given parameters."""


    @abstractmethod
    def run(self, **kwargs) -> str:
        """Execute the tool using the given arguments and return the result as a string."""
