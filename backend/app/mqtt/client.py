import asyncio
import ssl
from collections.abc import Awaitable, Callable, Mapping

import aiomqtt
import structlog

from app.core.config import Settings

log = structlog.get_logger()
SUBSCRIPTIONS = [
    ("edge/+/heartbeat", 0),
    ("edge/+/event", 1),
    ("edge/+/cmd/reply", 1),
]
Handler = Callable[[str, bytes], Awaitable[None]]


def valid_device_no(device_no: str) -> bool:
    return 0 < len(device_no) <= 64 and not any(char in device_no for char in "/+#\0")


class MqttClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: aiomqtt.Client | None = None
        self._connected = asyncio.Event()
        self._reconnect = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._client is not None

    async def run(self, handlers: Mapping[str, Handler]) -> None:
        settings = self.settings
        tls = settings.app_env in {"prod", "production"} or settings.mqtt_port == 8883
        delay = 1
        while True:
            try:
                async with aiomqtt.Client(
                    settings.mqtt_host,
                    port=settings.mqtt_port,
                    username=settings.mqtt_user or None,
                    password=settings.mqtt_pass.get_secret_value() if settings.mqtt_user else None,
                    tls_context=ssl.create_default_context() if tls else None,
                    timeout=2,
                ) as client:
                    grants = await client.subscribe(SUBSCRIPTIONS)
                    if any(code == 128 for code in grants):
                        raise aiomqtt.MqttError("Broker rejected an MQTT subscription")
                    delay = 1
                    log.info("mqtt_connected")
                    await self._listen(client, handlers)
            except (aiomqtt.MqttError, OSError) as exc:
                log.warning("mqtt_disconnected", error=str(exc), retry_in=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def _listen(self, client: aiomqtt.Client, handlers: Mapping[str, Handler]) -> None:
        self._client = client
        self._connected.set()
        messages = aiter(client.messages)
        reconnect = asyncio.create_task(self._reconnect.wait())
        incoming = asyncio.create_task(anext(messages))
        try:
            while True:
                done, _ = await asyncio.wait(
                    (incoming, reconnect), return_when=asyncio.FIRST_COMPLETED
                )
                if incoming in done:
                    await self._dispatch(incoming.result(), handlers)
                if self._reconnect.is_set():
                    return
                incoming = asyncio.create_task(anext(messages))
        except StopAsyncIteration:
            raise aiomqtt.MqttError("MQTT message stream closed") from None
        finally:
            self._client = None
            self._connected.clear()
            self._reconnect.clear()
            incoming.cancel()
            reconnect.cancel()
            await asyncio.gather(incoming, reconnect, return_exceptions=True)

    async def _dispatch(self, message: aiomqtt.Message, handlers: Mapping[str, Handler]) -> None:
        topic = str(message.topic)
        parts = topic.split("/", 2)
        if len(parts) != 3 or parts[0] != "edge":
            return
        _, device_no, kind = parts
        handler = handlers.get(kind)
        if handler is None or not valid_device_no(device_no):
            return
        if message.retain and kind == "cmd/reply":
            return
        try:
            await handler(device_no, message.payload)
        except Exception:
            log.exception("mqtt_handler_failed", topic=topic)

    async def publish(self, topic: str, payload: str) -> None:
        for attempt in range(2):
            while (client := self._client) is None:
                await self._connected.wait()
            try:
                await client.publish(topic, payload, qos=1)
                return
            except (aiomqtt.MqttError, OSError):
                if client is self._client:
                    self._client = None
                    self._connected.clear()
                    self._reconnect.set()
                if attempt:
                    raise
