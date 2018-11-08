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

"""Implement RESTful API endpoints using resources."""

from celery.result import AsyncResult
from flask_apispec import MethodResource, use_kwargs
from flask_apispec.extension import FlaskApiSpec
from cameo import models

from .celery import celery_app
from .schemas import PredictionJobRequestSchema
from .tasks import predict


class PredictionJobsResource(MethodResource):
    @use_kwargs(PredictionJobRequestSchema)
    def post(self, model_name, product_name, max_predictions):
        result = predict.delay(model_name, product_name, max_predictions)
        return {
            'id': result.id,
            'state': result.state,
        }, 202


class PredictionJobResource(MethodResource):
    def get(self, task_id):
        result = AsyncResult(id=task_id, app=celery_app)
        if not result.ready():
            return {
                'id': result.id,
                'state': result.state,
                'info': result.info,
            }, 202
        else:
            try:
                return {
                    'state': result.state,
                    'result': result.get(),
                }
            except Exception as e:
                return {
                    'state': result.state,
                    'exception': type(e).__name__,
                    'message': str(e),
                }


class ProductsResource(MethodResource):
    def get(self):
        return [{'name': m.name} for m in models.metanetx_universal_model_bigg_rhea.metabolites]


def init_app(app):
    """Register API resources on the provided Flask application."""
    def register(path, resource):
        app.add_url_rule(path, view_func=resource.as_view(resource.__name__))
        docs.register(resource, endpoint=resource.__name__)

    docs = FlaskApiSpec(app)
    register('/predict', PredictionJobsResource)
    register('/predict/<string:task_id>', PredictionJobResource)
    register('/products', ProductsResource)
