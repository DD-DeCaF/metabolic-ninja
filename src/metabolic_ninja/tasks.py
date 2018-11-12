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
from itertools import chain as iter_chain

import sentry_sdk
from cameo.api import design
from cameo.strain_design import DifferentialFVA, OptGene
from cameo.strain_design.heuristic.evolutionary.objective_functions import (
    biomass_product_coupled_min_yield, product_yield)
from cameo.strain_design.pathway_prediction import PathwayPredictor
from celery import group
from celery.utils.log import get_task_logger
from cobra.exceptions import OptimizationError
from cobra.io import model_from_dict
from cobra.io.dict import reaction_to_dict
from sentry_sdk.integrations.celery import CeleryIntegration
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .celery import celery_app
from .models import DesignJob
from .universal import UNIVERSAL_SOURCES


logger = get_task_logger(__name__)
# Initialize Sentry. Adding the celery integration will automagically report
# errors from all tasks.
sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[CeleryIntegration()],
)


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


@celery_app.task()
def fail_workflow(request, exc, traceback, job_id):
    with db_session() as session:
        job = session.query(DesignJob).filter_by(id=job_id).one()
        job.status = "FAILURE"
        session.add(job)
        session.commit()


@celery_app.task(bind=True)
def predict(self, model_obj, product_name, max_predictions, aerobic,
            databases, job_id):
    """
    Define and start a design prediction workflow.

    :param self:
    :param model_obj:
    :param product_name:
    :param max_predictions:
    :param aerobic:
    :param databases:
    :param job_id:
    :return:

    """
    # Update the job status.
    with db_session() as session:
        job = session.query(DesignJob).filter_by(id=job_id).one()
        job.status = 'STARTED'
        job.task_id = self.request.id
        session.add(job)
        session.commit()
    # Select the universal reaction database from the BiGG, RHEA pair.
    source = UNIVERSAL_SOURCES[databases]
    # Configure the model object for cameo.
    model = model_from_dict(model_obj["model_serialized"])
    model.solver = "cplex"
    if not aerobic and "EX_o2_e" in model.reactions:
        model.reactions.EX_o2_e.lower_bound = 0
    model.biomass = model_obj["default_biomass_reaction"]
    # We have to identify a carbon source from the medium.
    model.carbon_source = "EX_glc__D_e"
    # Define the workflow.
    workflow = (
        find_product.s(product_name, source) |
        find_pathways.s(model, max_predictions, source) |
        optimize.s(model) |
        concatenate.s() |
        persist.s(job_id)
    ).on_error(fail_workflow.s(job_id))
    return self.replace(workflow)


@celery_app.task()
def find_product(product_name, source):
    # Find the product name via the cameo designer. In a future far, far away
    # this should be a call to a web service.
    return design.translate_product_to_universal_reactions_model_metabolite(
        product_name, source
    )


@celery_app.task()
def find_pathways(product, model, max_predictions, source):
    predictor = PathwayPredictor(model, universal_model=source)
    return predictor.run(
        product,
        max_predictions=max_predictions,
        timeout=60,
        silent=True
    )


@celery_app.task(bind=True)
def optimize(self, pathways, model):
    return self.replace(group(
        (
            differential_fva_optimization.si(p, model) |
            evaluate_prediction.s(p, model, "PathwayPredictor+DifferentialFVA")
        )
        for p in pathways)
    )


@celery_app.task()
def differential_fva_optimization(pathway, model):
    with model:
        pathway.apply(model)
        predictor = DifferentialFVA(
            design_space_model=model,
            objective=pathway.product.id,
            variables=[model.biomass],
            points=10
        )
        try:
            designs = predictor.run(progress=False)
        except ZeroDivisionError as error:
            logger.warning("Encountered the following error in DiffFVA.",
                           exc_info=error)
            designs = None
    return designs


@celery_app.task()
def heuristic_optimization(pathway, model):
    with model:
        pathway.apply(model)
        predictor = OptGene(
            model=model,
            plot=False
        )
        designs = predictor.run(
            target=pathway.product.id,
            biomass=model.biomass,
            substrate=model.carbon_source,
            max_evaluations=1500,
            max_knockouts=15,
            max_time=120
        )
    return designs


@celery_app.task()
def evaluate_prediction(designs, pathway, model, method):
    if designs is None:
        return []
    pyield = product_yield(pathway.product, model.carbon_source)
    bpcy = biomass_product_coupled_min_yield(
        model.biomass, pathway.product, model.carbon_source)
    results = []
    with model:
        pathway.apply(model)
        for design_result in designs._designs:
            design_result.apply(model)
            try:
                model.objective = model.biomass
                solution = model.optimize()
                p_yield = pyield(model, solution, pathway.product)
                bpc_yield = bpcy(model, solution, pathway.product)
                target_flux = solution[pathway.product.id]
                biomass = solution[model.biomass]
            except (OptimizationError, ZeroDivisionError):
                p_yield = None
                bpc_yield = None
                target_flux = None
                biomass = None
            results.append({
                "manipulations": design_result,
                "heterologous_reactions": pathway.reactions,
                "synthetic_reactions": pathway.exchanges,
                "fitness": bpc_yield,
                "yield": p_yield,
                "product": target_flux,
                "biomass": biomass,
                "method": method
            })
    return results


@celery_app.task()
def concatenate(results):
    reactions = {}
    final = []
    # Flatten lists and convert design and pathway to dictionary.
    for row in iter_chain.from_iterable(results):
        reactions.update(**{
            r.id: reaction_to_dict(r) for r in row["heterologous_reactions"]
        })
        row["manipulations"] = [
            t._repr_html_() for t in row["manipulations"].targets]
        row["heterologous_reactions"] = [
            r.id for r in row["heterologous_reactions"]]
        row["synthetic_reactions"] = [
            r.id for r in row["synthetic_reactions"]]
        final.append(row)
    return {
        "table": final,
        "reactions": reactions
    }


@celery_app.task()
def persist(result, job_id):
    with db_session() as session:
        job = session.query(DesignJob).filter_by(id=job_id).one()
        job.status = "SUCCESS"
        job.result = result
        session.add(job)
        session.commit()
    return result
