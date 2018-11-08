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
from contextlib import contextmanager

import sentry_sdk
from cameo.api import design
from cameo.models import universal
from cameo.parallel import MultiprocessingView
from celery.signals import task_postrun, task_prerun
from celery.utils.log import get_task_logger
from cobra.io import model_from_dict
from sentry_sdk.integrations.celery import CeleryIntegration
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .celery import celery_app
from .models import DesignJob


logger = get_task_logger(__name__)
# Initialize Sentry. Adding the celery integration will automagically report
# errors from all tasks.
sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[CeleryIntegration()],
)
# Timeouts are given in minutes.
design.options.pathway_prediction_timeout = 60
design.options.heuristic_optimization_timeout = 120
design.options.differential_fva = True
design.options.heuristic_optimization = True
design.options.differential_fva_points = 10
design.database = universal.metanetx_universal_model_bigg_rhea


@contextmanager
def db_session():
    """Connect to the database and yield an SA session."""
    engine = create_engine(
        'postgresql://{POSTGRES_USERNAME}:{POSTGRES_PASS}@{POSTGRES_HOST}:'
        '{POSTGRES_PORT}/{POSTGRES_DB_NAME}'.format(**os.environ)
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@task_prerun.connect
def task_prerun_handler(**kwargs):
    with db_session() as session:
        job_id = kwargs['args'][0]
        job = session.query(DesignJob).filter_by(id=job_id).one()
        job.status = 'STARTED'
        job.task_id = kwargs['task'].request.id
        session.add(job)
        session.commit()


@task_postrun.connect
def task_postrun_handler(**kwargs):
    with db_session() as session:
        job_id = kwargs['args'][0]
        job = session.query(DesignJob).filter_by(id=job_id).one()
        job.status = kwargs['state']
        session.add(job)
        session.commit()


@celery_app.task
def predict(job_id, model_obj, product, max_predictions, aerobic):
    model = model_from_dict(model_obj)
    design.options.max_pathway_predictions = max_predictions
    view = MultiprocessingView(processes=3)
    reports = design(
        product=product,
        database=universal.metanetx_universal_model_bigg_rhea,
        hosts=[model],
        view=view,
        aerobic=aerobic
    )
    return reports
