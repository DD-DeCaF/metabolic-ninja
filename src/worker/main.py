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
import json
import pika
import os
import signal

from . import tasks
from .data import Job


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


def on_message(channel, method, properties, body):
    logger.debug(f"Received new job")
    job = Job.deserialize(json.loads(body))
    tasks.design(job)
    channel.basic_ack(delivery_tag=method.delivery_tag)


def on_terminate(channel, signum, frame):
    logger.debug(f"Caught SIGTERM, cancelling consumption")
    channel.stop_consuming()


def main():
    logger.debug("Establishing connection and declaring task queue")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            # Disable heartbeat to ensure that connections aren't broken during
            # long-running jobs.
            host=os.environ["RABBITMQ_HOST"], heartbeat=None
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue="jobs", durable=True)
    # Prefetch only a single message, to ensure messages aren't sent to busy
    # workers.
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="jobs", on_message_callback=on_message)

    # Register the signal handler
    signal.signal(signal.SIGTERM, functools.partial(on_terminate, channel))

    logger.info("Waiting for messages")
    channel.start_consuming()


if __name__ == "__main__":
    main()
