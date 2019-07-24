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

"""
Periodically check disk usage for the redis drive at /var/lib/rabbitmq.

If the free disk space is lower than the threshold, log an error event to be
reported to Sentry for notification.
"""

import logging
import logging.config
import os
import signal
import sys
import time

import sentry_sdk


def handle_signal(sig, frame):
    logger.info("Handling signal: SIGTERM; exiting.")
    sys.exit(0)


logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
            }
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "simple",
            }
        },
        "root": {"level": "DEBUG", "handlers": ["console"]},
    }
)
logger = logging.getLogger("disk-usage")
sentry_sdk.init(os.environ["SENTRY_DSN"])
signal.signal(signal.SIGTERM, handle_signal)


while True:
    st = os.statvfs("/var/lib/rabbitmq")
    pct_free = round(st.f_bfree / st.f_blocks * 100)
    total_gb = round((st.f_bsize * st.f_blocks) / 1024 / 1024 / 1024)
    free_gb = round((st.f_bsize * st.f_bfree) / 1024 / 1024 / 1024)
    usage_gb = total_gb - free_gb
    size_display = f"{pct_free}% ({free_gb} GB / {total_gb} GB)"
    if pct_free < 25:
        logger.error(
            f"Warning: Disk usage is below {pct_free}% free, at {usage_gb}GB "
            f"out of {total_gb}GB, in the redis persistent storage for "
            "metabolic ninja. Consider running BGREWRITEAOF."
        )
    logger.info(
        f"Disk usage: {usage_gb}GB/{total_gb}GB ({pct_free}% free), sleeping..."
    )
    time.sleep(60 * 60)  # sleep 1 hour
