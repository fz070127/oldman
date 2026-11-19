from app.models.enums import Channel
from app.services.notify.mock import UnconfiguredNotifier


class PushNotifier(UnconfiguredNotifier):
    """JPush/Getui integration point."""

    channel = Channel.PUSH
    provider = "jpush/getui"
