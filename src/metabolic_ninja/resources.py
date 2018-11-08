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
from flask import g
from flask_apispec import MethodResource, use_kwargs
from flask_apispec.extension import FlaskApiSpec
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import Forbidden, NotFound, Unauthorized

from .app import app
from .celery import celery_app
from .jwt import jwt_require_claim, jwt_required
from .models import DesignJob, db
from .schemas import PredictionJobRequestSchema
from .tasks import predict


class PredictionJobsResource(MethodResource):

    @jwt_required
    @use_kwargs(PredictionJobRequestSchema)
    def post(self, model_id, project_id, product_name, max_predictions,
             aerobic=False):
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
            "Authorization": g.jwt_token,
        })
        # Verify that the user may actually start a job for the given project
        # identifier.
        jwt_require_claim(project_id, "write")

        # Job accepted. Before submitting the job, create a corresponding empty
        # db entry.
        job = DesignJob(project_id=project_id, model_id=model_id,
                        status='PENDING')
        db.session.add(job)
        db.session.commit()
        result = predict.delay(job.id, model, product_name, max_predictions,
                               aerobic)
        return {
            'id': job.id,
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
        return response.json()['model_serialized']

    def get(self):
        # Return a list of jobs that the user can see.
        pass


class PredictionJobResource(MethodResource):

    def get(self, job_id):
        try:
            job = DesignJob.query.filter(
                DesignJob.id == job_id,
            ).filter(
                DesignJob.project_id.in_(g.jwt_claims['prj']) |
                DesignJob.project_id.is_(None)
            ).one()
        except NoResultFound:
            return {'error': f"Cannot find any model with id {job_id}"}, 404
        else:
            if job.is_complete():
                status = 200
            else:
                status = 202
            return {
                'id': job.id,
                'task_id': job.task_id,
                'status': job.status,
                'result': job.result,
            }, status


def init_app(app):
    """Register API resources on the provided Flask application."""
    def register(path, resource):
        app.add_url_rule(path, view_func=resource.as_view(resource.__name__))
        docs.register(resource, endpoint=resource.__name__)

    docs = FlaskApiSpec(app)
    register('/predictions', PredictionJobsResource)
    register('/predictions/<string:job_id>', PredictionJobResource)
