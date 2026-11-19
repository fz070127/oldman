from app.models import Alarm


async def notify_new_alarm(alarm: Alarm) -> None:
    # TODO(M6): deliver the notification after the alarm transaction commits.
    pass
