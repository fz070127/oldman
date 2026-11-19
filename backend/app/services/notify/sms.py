from app.models.enums import Channel
from app.services.notify.mock import UnconfiguredNotifier


class SmsNotifier(UnconfiguredNotifier):
    """Aliyun SMS integration point."""

    channel = Channel.SMS
    provider = "aliyun"
