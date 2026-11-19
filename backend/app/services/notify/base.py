from abc import ABC, abstractmethod
from typing import NamedTuple


class NotifyResult(NamedTuple):
    success: bool
    channel: str
    detail: dict


class Notifier(ABC):
    channel: str

    @abstractmethod
    async def send(self, to: str, title: str, content: str, ctx: dict) -> NotifyResult:
        """Deliver to a channel address and report the result."""
