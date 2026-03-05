import json
import logging

from confluent_kafka import Producer

from app.core.config import settings
from app.logging_utils import Events, log_event

logger = logging.getLogger(__name__)


class KafkaPublisher:
    def __init__(self) -> None:
        self._producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})

    def publish(self, topic: str, key: str, payload: dict) -> None:
        message = json.dumps(payload)
        log_event(
            logger,
            logging.INFO,
            Events.KAFKA_PUBLISH_REQUEST,
            component="kafka_producer",
            topic=topic,
            key=key,
            payload_size=len(message),
        )

        def delivery_report(err, msg) -> None:
            if err is not None:
                log_event(
                    logger,
                    logging.ERROR,
                    Events.KAFKA_PUBLISH_FAILED,
                    component="kafka_producer",
                    topic=topic,
                    key=key,
                    error=str(err),
                )
            else:
                log_event(
                    logger,
                    logging.INFO,
                    Events.KAFKA_PUBLISH_ACK,
                    component="kafka_producer",
                    topic=msg.topic(),
                    partition=msg.partition(),
                    offset=msg.offset(),
                    key=key,
                )

        self._producer.produce(topic=topic, key=key, value=message, callback=delivery_report)
        self._producer.flush()

    def close(self) -> None:
        self._producer.flush()


publisher = KafkaPublisher()
