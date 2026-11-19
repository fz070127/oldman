"""One FIFO QoS 1 sender per device. The capture thread never waits for a broker."""
import json
import logging
import threading
import time

import paho.mqtt.client as mqtt

from local_store import LocalStore


class Publisher:
    def __init__(self, device, config, db_path):
        self.device = device
        self.topic = f"{config.get('topic_prefix', 'edge').strip('/')}/{device}"
        self.store = LocalStore(db_path)
        self.online = threading.Event()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=device)
        self.client.on_connect = self._connected
        self.client.on_disconnect = self._disconnected
        self.client.reconnect_delay_set(1, 15)
        self.client.max_queued_messages_set(1)
        self.client.connect_async(config["host"], int(config.get("port", 1883)), 30)
        self.client.loop_start()
        self.worker = threading.Thread(target=self._send, name="mqtt-outbox")
        self.worker.start()

    def _connected(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            logging.warning("MQTT rejected %s", reason_code)
        else:
            logging.info("MQTT connected %s", self.device)
            self.online.set()
            self.wake.set()

    def _disconnected(self, client, userdata, flags, reason_code, properties):
        self.online.clear()
        logging.info("MQTT disconnected %s (%s)", self.device, reason_code)

    def report(self, event):
        self.store.add(event)
        logging.warning("本地已报警\a device=%s eventId=%s level=%s",
                        self.device, event["eventId"], event["level"])
        self.wake.set()

    def heartbeat(self, payload):
        if self.online.is_set():
            self.client.publish(self.topic + "/heartbeat", json.dumps(payload), qos=0)

    def _send(self):
        while not self.stop.is_set():
            self.wake.clear()
            row = self.store.oldest() if self.online.is_set() else None
            if row is None:
                self.wake.wait(1)
                continue
            key, encoded = row
            publish_mono = time.perf_counter()
            info = self.client.publish(self.topic + "/event", encoded, qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                self.stop.wait(0.25)
                continue
            # Paho retries this in-flight QoS 1 packet across reconnects.
            while not self.stop.is_set() and not info.is_published():
                info.wait_for_publish(timeout=0.25)
            if info.is_published():
                self.store.acknowledged(key)
                logging.info("MQTT PUBACK eventId=%s publish_mono=%.9f", key, publish_mono)

    def close(self):
        self.stop.set()
        self.wake.set()
        self.worker.join()
        self.client.disconnect()
        self.client.loop_stop()
        self.store.close()
