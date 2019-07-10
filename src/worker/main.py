# Copyright (c) 2018, Novo Nordisk Foundation Center for Biosustainability,
# Technical University of Denmark.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import functools
import logging
import logging.config
import pika
import os
import signal
import threading
import sys

import sentry_sdk

from . import tasks


logger = logging.getLogger(__name__)
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": (
                    "%(asctime)s [%(levelname)s] %(name)s::%(funcName)s:%(lineno)d | "
                    "%(message)s"
                )
            }
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "simple",
            }
        },
        "loggers": {
            # All loggers will by default use the root logger below (and
            # hence be very verbose). To silence spammy/uninteresting log
            # output, add the loggers here and increase the loglevel.
            "pika": {"level": "WARNING", "handlers": ["console"]}
        },
        "root": {"level": "DEBUG", "handlers": ["console"]},
    }
)
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"))
# Ignore some verbose loggers from pika (relevant when unable to connect, but we handle
# that anyway).
sentry_sdk.integrations.logging.ignore_logger(
    "pika.adapters.utils.io_services_utils"
)
sentry_sdk.integrations.logging.ignore_logger(
    "pika.adapters.utils.connection_workflow"
)
sentry_sdk.integrations.logging.ignore_logger(
    "pika.adapters.blocking_connection"
)

# Whenever a job is received, the work on it will be started in a new thread. This is
# to allow the RabbitMQ i/o loop to do its thing (like sending hearbeats to the server
# to keep the connection alive). Started threads are stored in this list, so that we can
# wait for the threads to complete when terminating the application.
worker_threads = []


def on_message(channel, method_frame, header_frame, body, connection):
    """Callback to receive new messages from RabbitMQ."""
    logger.debug(f"Received message {method_frame.delivery_tag}")
    # Start the work in a separate thread, to avoid blocking the pika i/o loop.
    thread = threading.Thread(
        target=tasks.design,
        args=(
            connection,
            channel,
            method_frame.delivery_tag,
            body,
            ack_message,
        ),
    )
    thread.start()
    worker_threads.append(thread)


def ack_message(channel, delivery_tag):
    """Callback to ACK a finished job."""
    # If the channel was closed for some reason, ignore.
    logger.debug(f"ACKing message {delivery_tag}")
    if channel.is_open:
        channel.basic_ack(delivery_tag)


def on_terminate(channel, signum, frame):
    """SIGTERM signal handler to terminate the application."""
    logger.debug(f"Caught SIGTERM, cancelling consumption")
    channel.stop_consuming()


def main():
    logger.debug("Establishing connection and declaring task queue")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"])
        )
    except pika.exceptions.AMQPConnectionError:
        # Connection failed - exit and rely on the environment to restart the
        # application. Don't let the exception bubble though; we don't need a Sentry
        # notification for this.
        logger.warning(
            "AMQPConnectionError: Cannot connect to RabbitMQ. Aborting."
        )
        sys.exit(-1)

    channel = connection.channel()
    channel.queue_declare(queue="jobs", durable=True)
    # Prefetch only a single message, to ensure messages aren't sent to busy
    # workers.
    channel.basic_qos(prefetch_count=1)
    # Pass the connection to the message callback - it'll be needed later to ACK
    # messages.
    callback = functools.partial(on_message, connection=connection)
    channel.basic_consume(queue="jobs", on_message_callback=callback)

    # Register the signal handler
    signal.signal(signal.SIGTERM, functools.partial(on_terminate, channel))

    logger.info("Ready for action, waiting for messages from RabbitMQ")
    channel.start_consuming()

    logger.info(
        "Pika consumption loop exited. Cleaning up and terminating application..."
    )

    # Wait for any worker threads to complete
    for thread in worker_threads:
        thread.join()

    connection.close()


if __name__ == "__main__":
    main()
