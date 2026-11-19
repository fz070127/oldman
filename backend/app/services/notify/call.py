from app.models.enums import Channel
from app.services.notify.mock import UnconfiguredNotifier


class CallNotifier(UnconfiguredNotifier):
    """Voice call integration point."""

    channel = Channel.CALL
    provider = "aliyun"
