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

from cameo import models
from cameo.strain_design import pathway_prediction
from celery import chain
from cobra.io.dict import reaction_to_dict

from .celery import celery_app
from .models import DesignJob


def design(project_id, model_id, model, product_name, max_predictions):
    res = chain(
        save_job(project_id, model_id) |
        find_product(product_name) |
        find_pathways(model, max_predictions) |
        # Check current cameo workflow. Either apply optimizations
        # sequentially or in a parallel group.
        optimize(model) |
        save_result()
    )
    return res


# TODO: Make sure that `self.id` corresponds to the chain ID.
@celery_app.task(bind=True, ignore_result=True)
def save_job(self, project_id, model_id):
    # Create a session.
    # session =
    job = DesignJob(project_id=project_id, model_id=model_id, task_id=self.id)
    # session.add(job)
    # session.commit()


@celery_app.task()
def find_product(product_name):
    # Find the product name via MetaNetX.
    return product_name


@celery_app.task()
def find_pathways(product, model, max_predictions):
    predictor = pathway_prediction.PathwayPredictor(model)
    pathways = predictor.run(product=product, max_predictions=max_predictions)
    return pathways


@celery_app.task()
def optimize(pathways, model):
    # Run optimizations on each pathway applied to the model.
    results = []
    for path in pathways:
        with model:
            path.plug_model(model)
            # optimize
            results.append()
    return results


# TODO: Make sure that `self.id` corresponds to the chain ID.
@celery_app.task(bind=True, ignore_result=True)
def save_result(self, results):
    # Create a session.
    # session =
    job = session.query(DesignJob).filter(task_id=self.id).one()
    job.is_complete = True
    job.result = results
    session.add(job)
    session.commit()
