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
from cameo.strain_design.pathway_prediction import PathwayPredictor
from cameo.util import IntelliContainer
from celery import chain
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


UNIVERSAL_SOURCES = {
    (True, False): universal.metanetx_universal_model_bigg,
    (True, True): universal.metanetx_universal_model_bigg_rhea,
    (False, True): universal.metanetx_universal_model_rhea,
}


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
        job.result = kwargs['result']
        session.add(job)
        session.commit()


@celery_app.task()
def find_product(product_name, databases=(True, True)):
    source = UNIVERSAL_SOURCES[databases]
    # Find the product name via the cameo designer. In a future far, far away
    # this should be a call to a web service.
    return design.translate_product_to_universal_reactions_model_metabolite(
        product_name, source
    ), source


@celery_app.task()
def find_pathways(model_obj, max_predictions, aerobic, previous):
    product, source = previous
    model = model_from_dict(model_obj["model_serialized"])
    if not aerobic and "EX_o2_e" in model.reactions:
        model.reactions.EX_o2_e.lower_bound = 0
    predictor = PathwayPredictor(model, universal_model=source)
    return predictor.run(
        product,
        max_predictions=max_predictions,
        timeout=60,
        silent=True
    ), source


@celery_app.task()
def optimize(aerobic, pathways):
    # Run optimizations on each pathway applied to the model.
    reports = design.optimize_strains(pathways, aerobic=aerobic)
    return reports


@celery_app.task
def predict(model_obj, product, max_predictions, aerobic):
    # Initialize a cameo host with an `IntelliContainer` which basically
    # works like a `dict`.
    host = Host(name=model_obj["organism_id"], models=IntelliContainer())
    model = model_from_dict(model_obj["model_serialized"])
    model.solver = "cplex"
    # We add more attributes for cameo.
    model.biomass = model_obj["default_biomass_reaction"]
    # We have to identify a carbon source from the medium.
    model.carbon_source = None
    host.models[model_obj["name"]] = model
    design.options.max_pathway_predictions = max_predictions
    view = MultiprocessingView(processes=3)
    reports = design(
        product=product,
        database=universal.metanetx_universal_model_bigg_rhea,
        hosts=[host],
        view=view,
        aerobic=aerobic
    )
    return reports


@celery_app.task
def prediction_to_json(reports):
    pass


@celery_app.task(bind=True, ignore_result=True)
def save_result(self, results):
    with db_session() as session:
        job = session.query(DesignJob).filter_by(task_id=self.request.id).one()
        job.result = results
        job.is_complete = True
        job.status = self.state
        session.add(job)
        session.commit()
