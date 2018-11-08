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
from time import sleep

from cameo.api import design
from cameo.models import universal
from cameo.parallel import MultiprocessingView
from celery import chain
from celery.utils.log import get_task_logger
from cobra.io import model_from_dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from .celery import celery_app
from .models import DesignJob


logger = get_task_logger(__name__)
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


def design_flow(model_obj, product_name, max_predictions, aerobic):
    """Define a workflow and return its AsyncResult."""
    chain_def = chain(
        # TODO: Move save_job here.
        predict.s(model_obj, product_name, max_predictions, aerobic) |
        save_result.s()
    )
    return chain_def()


@celery_app.task(ignore_result=True)
def save_job(project_id, model_id, uuid):
    result = celery_app.AsyncResult(uuid)
    with db_session() as session:
        job = DesignJob(project_id=project_id, model_id=model_id,
                        task_id=result.id, status=result.state)
        session.add(job)
        session.commit()


@celery_app.task
def predict(model_obj, product, max_predictions, aerobic):
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


@celery_app.task(bind=True, ignore_result=True)
def save_result(self, results):
    with db_session() as session:
        job = session.query(DesignJob).filter_by(task_id=self.request.id).one()
        job.result = results
        job.status = self.state
        session.add(job)
        session.commit()


@celery_app.task
def error_handler(uuid):
    """

    See also
    http://docs.celeryproject.org/en/latest/userguide/calling.html#linking-callbacks-errbacks

    """
    result = celery_app.AsyncResult(uuid)
    exception = result.get(propagate=False)
    logger.error(exc_info=exception)
    # Log to sentry.
    # Store job as failed.
    with db_session() as session:
        is_pending = True
        job = None
        # Wait for save_job to complete.
        while is_pending:
            try:
                job = session.query(DesignJob).filter_by(task_id=result.id).one()
                is_pending = False
            except NoResultFound:
                sleep(2)
        if job is not None:
            job.status = result.state
            session.add(job)
            session.commit()
