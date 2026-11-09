import json
import logging
import os
import time
from .projector import ProjectionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("consumer")


def run_forever():
    import pika
    store = ProjectionStore(os.getenv("QUERY_DB", "/tmp/ecorescate/query.sqlite3"))
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/%2F")
    while True:
        try:
            conn = pika.BlockingConnection(pika.URLParameters(url))
            channel = conn.channel()
            channel.exchange_declare(exchange="ecorescate.events", exchange_type="topic", durable=True)
            channel.queue_declare(queue="ecorescate.readmodel", durable=True)
            channel.queue_bind(exchange="ecorescate.events", queue="ecorescate.readmodel", routing_key="offer.*")
            channel.basic_qos(prefetch_count=10)

            def on_message(ch, method, props, body):
                try:
                    store.apply(json.loads(body))
                    ch.basic_ack(method.delivery_tag)
                except (ValueError, KeyError, json.JSONDecodeError):
                    LOG.exception("Evento inválido, se descarta para evitar reintentos infinitos")
                    ch.basic_reject(method.delivery_tag, requeue=False)
                except Exception:
                    LOG.exception("Error transitorio: el evento se reprocesará")
                    ch.basic_nack(method.delivery_tag, requeue=True)
                    time.sleep(1)

            channel.basic_consume(queue="ecorescate.readmodel", on_message_callback=on_message)
            LOG.info("Escuchando eventos EcoRescate")
            channel.start_consuming()
        except Exception:
            LOG.exception("RabbitMQ no disponible; se reintentará")
            time.sleep(3)
        finally:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    run_forever()
