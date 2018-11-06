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

import requests
from celery.result import AsyncResult
from flask_apispec import MethodResource, use_kwargs
from flask_apispec.extension import FlaskApiSpec
from werkzeug.exceptions import Unauthorized, Forbidden, NotFound

from .app import app
from .celery import celery_app
from .schemas import JWTSchema, PredictionJobRequestSchema
from .tasks import design
from .jwt import jwt_require_claim


class PredictionJobsResource(MethodResource):
    @use_kwargs(PredictionJobRequestSchema)
    @use_kwargs(JWTSchema(), location="headers")
    def post(self, model_id, project_id, product_name, max_predictions, token):
        """
        Create a design job.

        :param model_id: A numeric identifier coming from the model-storage
            service.
        :param project_id: Can be ``None`` in which case the job is public.
        :param product_name:
        :param max_predictions:
        :param token: Value extracted from the request 'Authorization' header.
        :return:
        """
        # Verify the request by loading the model from the model-storage
        # service.
        model = self.retrieve_model_json(model_id, {
                "Authorization": token
            })
        # Verify that the user may actually start a job for the given project
        # identifier.
        jwt_require_claim(project_id, "write")
        result = predict.delay(project_id, model, product_name, max_predictions)
        return {
            'id': result.id,
            'state': result.state,
        }, 202

    @staticmethod
    def retrieve_model_json(model_id, headers):
        response = requests.get(
            f'{app.config["MODEL_STORAGE_API"]}/models/{model_id}',
            headers=headers)
        if response.status_code == 401:
            message = response.json().get('message', "No error message")
            raise Unauthorized(f"Invalid credentials ({message}).")
        elif response.status_code == 403:
            message = response.json().get('message', "No error message")
            raise Forbidden(f"Insufficient permissions to access model "
                            f"{model_id} ({message}).")
        elif response.status_code == 404:
            raise NotFound(f"No model with id {model_id}.")
        # In case any unexpected errors occurred this will trigger an
        # internal server error.
        response.raise_for_status()
        return response.json()


class PredictionJobResource(MethodResource):
    def get(self, task_id):
        result = AsyncResult(id=task_id, app=celery_app)
        if not result.ready():
            return {
                'id': result.id,
                'state': result.state,
            }, 202
        else:
            try:
                return {
                    'state': result.state,
                    'result': result.get(),
                }
            except Exception as error:
                return {
                    'state': result.state,
                    'exception': type(error).__name__,
                    'message': str(error),
                }


def init_app(app):
    """Register API resources on the provided Flask application."""
    def register(path, resource):
        app.add_url_rule(path, view_func=resource.as_view(resource.__name__))
        docs.register(resource, endpoint=resource.__name__)

    docs = FlaskApiSpec(app)
    register('/predict', PredictionJobsResource)
    register('/predict/<string:task_id>', PredictionJobResource)
