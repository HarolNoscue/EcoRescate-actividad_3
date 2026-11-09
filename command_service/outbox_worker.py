import json
import logging
import os
import time
from .sqlite_adapter import SQLiteOfferRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("outbox")
EXCHANGE = "ecorescate.events"
QUEUE = "ecorescate.readmodel"


def run_forever():
    import pika  # En tests del dominio no se necesita instalar el broker.
    repo = SQLiteOfferRepository(os.getenv("COMMAND_DB", "/tmp/ecorescate/command.sqlite3"))
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/%2F")
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(url))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            channel.queue_declare(queue=QUEUE, durable=True)
            channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key="offer.*")
            channel.confirm_delivery()
            while True:
                records = repo.pending_outbox()
                for record in records:
                    event = json.loads(record["payload"])
                    channel.basic_publish(
                        exchange=EXCHANGE, routing_key=event["event_type"],
                        body=record["payload"].encode(), mandatory=True,
                        properties=pika.BasicProperties(delivery_mode=2,
                                                        content_type="application/json",
                                                        message_id=event["event_id"]))
                    repo.mark_published(record["seq"])
                time.sleep(0.5)
        except Exception:
            LOG.exception("Fallo publicando eventos; se reintentará sin perder el outbox")
            time.sleep(3)
        finally:
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    run_forever()
