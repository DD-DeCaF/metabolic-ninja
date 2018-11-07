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

"""Test expected functioning of the celery tasks."""

import metabolic_ninja.tasks as tasks
from metabolic_ninja.models import DesignJob


def test_save_job(celery_worker, celery_app, session):
    result = celery_app.AsyncResult("foo")
    tmp = tasks.save_job.delay(1, 2, result.id)
    # Wait for completion.
    tmp.get()
    job = session.query(DesignJob).filter_by(task_id=result.id).one()
    assert job.project_id == 1
    assert job.model_id == 2

