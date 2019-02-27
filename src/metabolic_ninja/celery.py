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

import os

from celery import Celery


celery_app = Celery(
    'metabolic_ninja_worker',
    broker=f'redis://{os.environ["REDIS_HOST"]}/0',
    backend=f'redis://{os.environ["REDIS_HOST"]}/1',
)

celery_app.conf.update(
    task_track_started=True,
    # Time after which a running job will be interrupted.
    task_time_limit=7200,  # 2 hours
    # Time after which a successful result will be removed.
    result_expires=604800,  # 7 days
    # Reboot worker processes if consuming too much memory. This is a workaround
    # for expected memory leak in the cameo workflow.
    worker_max_memory_per_child=(1.5 * 1000 * 1000),  # 1.5 GB
    # Our tasks are expected to be mostly cpu bound, so the number of concurrent
    # processes is set to match the number of cores available in the deployment
    # configuration, currently 4 vCPUs.
    worker_concurrency=int(os.environ['WORKER_CONCURRENCY']),
    task_serializer='pickle',
    result_serializer='pickle',
    accept_content=['pickle']
)
