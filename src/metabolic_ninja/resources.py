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

import json
import logging
import os

import requests
from flask import g, make_response
from flask_apispec import MethodResource, marshal_with, use_kwargs
from flask_apispec.extension import FlaskApiSpec
from pandas import DataFrame
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import Forbidden, NotFound, Unauthorized

from .app import app
from .jwt import jwt_require_claim, jwt_required
from .models import DesignJob, db
from .rabbitmq import submit_job
from .schemas import PredictionJobRequestSchema, PredictionJobSchema


logger = logging.getLogger(__name__)

with open("data/products.json") as file_:
    PRODUCT_LIST = json.load(file_)


class PredictionJobsResource(MethodResource):
    @jwt_required
    @use_kwargs(PredictionJobRequestSchema)
    def post(
        self,
        organism_id,
        model_id,
        project_id,
        product_name,
        max_predictions,
        bigg,
        rhea,
        aerobic,
    ):
        """
        Create a design job.

        :param model_id: A numeric identifier coming from the model-storage
            service.
        :param project_id: Can be ``None`` in which case the job is public.
        :param product_name:
        :param max_predictions:
        :param bigg: bool
        :param rhea: bool
        :param aerobic: bool
        :return:
        random comment
        """
        # Verify that the user may actually start a job for the given project
        # identifier.
        jwt_require_claim(project_id, "write")
        # Verify the request by loading the model from the model-storage
        # service.
        headers = {"Authorization": f"Bearer {g.jwt_token}"}
        model = self.retrieve_model_json(model_id, headers)
        # Job accepted. Before submitting the job, create a corresponding empty
        # database entry.
        job = DesignJob(
            project_id=project_id,
            organism_id=organism_id,
            model_id=model_id,
            product_name=product_name,
            max_predictions=max_predictions,
            aerobic=aerobic,
            status="PENDING",
        )
        db.session.add(job)
        db.session.commit()
        logger.debug(f"Created pending job with ID {job.id}")
        # Fetch details about the user and organism name, to be used in the
        # notification email. This must be done here while the token is still
        # valid.
        response = requests.get(
            f"{os.environ['IAM_API']}/user",
            headers={"Authorization": f"Bearer {g.jwt_token}"},
        )
        response.raise_for_status()
        user = response.json()
        user_name = f"{user['first_name']} {user['last_name']}"
        user_email = user["email"]
        # Retrieve the organism name.
        response = requests.get(
            f"{os.environ['WAREHOUSE_API']}/organisms/{organism_id}",
            headers={"Authorization": f"Bearer {g.jwt_token}"},
        )
        response.raise_for_status()
        organism_name = response.json()["name"]
        # Submit a prediction to the rabbitmq queue.
        submit_job(
            model=model,
            product_name=product_name,
            max_predictions=max_predictions,
            aerobic=aerobic,
            bigg=bigg,
            rhea=rhea,
            job_id=job.id,
            organism_id=organism_id,
            organism_name=organism_name,
            user_name=user_name,
            user_email=user_email,
        )
        return {"id": job.id}, 202

    @staticmethod
    def retrieve_model_json(model_id, headers):
        response = requests.get(
            f'{app.config["MODEL_STORAGE_API"]}/models/{model_id}',
            headers=headers,
        )
        if response.status_code == 401:
            message = response.json().get("message", "No error message")
            raise Unauthorized(f"Invalid credentials ({message}).")
        elif response.status_code == 403:
            message = response.json().get("message", "No error message")
            raise Forbidden(
                f"Insufficient permissions to access model "
                f"{model_id} ({message})."
            )
        elif response.status_code == 404:
            raise NotFound(f"No model with id {model_id}.")
        # In case any unexpected errors occurred this will trigger an
        # internal server error.
        response.raise_for_status()
        return response.json()

    @marshal_with(PredictionJobSchema(many=True, exclude=("result",)), 200)
    def get(self):
        # Return a list of jobs that the user can see.
        return DesignJob.query.filter(
            DesignJob.project_id.in_(g.jwt_claims["prj"])
            | DesignJob.project_id.is_(None)
        ).all()


class PredictionJobResource(MethodResource):
    @marshal_with(PredictionJobSchema(), 200)
    @marshal_with(PredictionJobSchema(), 202)
    def get(self, job_id):
        job_id = int(job_id)
        try:
            job = (
                DesignJob.query.filter(DesignJob.id == job_id)
                .filter(
                    DesignJob.project_id.in_(g.jwt_claims["prj"])
                    | DesignJob.project_id.is_(None)
                )
                .one()
            )
        except NoResultFound:
            return (
                {"error": f"Cannot find any design job with id {job_id}."},
                404,
            )
        else:
            if job.is_complete():
                status = 200
            else:
                status = 202
            return job, status


class ProductsResource(MethodResource):
    def get(self):
        return PRODUCT_LIST


class PathwayResource(MethodResource):
    def get(self, job_id, pathway_id):
        job_id = int(job_id)
        try:
            job = (
                DesignJob.query.filter(DesignJob.id == job_id)
                .filter(
                    DesignJob.project_id.in_(g.jwt_claims["prj"])
                    | DesignJob.project_id.is_(None)
                )
                .one()
            )
        except NoResultFound:
            return (
                {"error": f"Cannot find any design job with id {job_id}."},
                404,
            )
        else:
            if job.is_complete():
                status = 200
            else:
                status = 202
            pathway = next(
                (
                    x
                    for x in job.result["diff_fva"]
                    + job.result["opt_gene"]
                    + job.result["cofactor_swap"]
                    if x["id"] == pathway_id
                ),
                None,
            )
            if not pathway:
                return (
                    {"error": f"Cannot find any job result with id {pathway_id}."},
                    404,
                )
            result = get_tabular_data(pathway)
            response = make_response(result, status)
            response.headers["Content-Type"] = "text/csv"
            response.headers["Content-Disposition"] = "attachment"
            return response


def get_tabular_data(pathway):
    result = []
    targets = pathway["targets"]
    manipulations = pathway["manipulations"]
    if pathway["method"] == "PathwayPredictor+DifferentialFVA":
        for t in manipulations:
            rxn_id = t["id"]
            rxn_data = {"reaction_target": rxn_id}
            rxn_data["reaction_name"] = targets[rxn_id]["name"]
            rxn_data["subsystem"] = targets[rxn_id]["subsystem"]
            rxn_data["gpr"] = targets[rxn_id]["gpr"]
            rxn_data["definition_of_stoichiometry"] = targets[rxn_id][
                "definition_of_stoichiometry"
            ]
            rxn_data["new_flux_level"] = t["value"]
            rxn_data["score"] = t["score"]
            rxn_data["knockout"] = targets[rxn_id]["knockout"]
            rxn_data["flux_reversal"] = targets[rxn_id]["flux_reversal"]
            rxn_data["suddenly_essential"] = targets[rxn_id][
                "suddenly_essential"
            ]
            result.append(rxn_data)
        df = DataFrame(
            result,
            columns=[
                "reaction_target",
                "reaction_name",
                "subsystem",
                "gpr",
                "definition_of_stoichiometry",
                "new_flux_level",
                "score",
                "knockout",
                "flux_reversal",
                "suddenly_essential",
            ],
        )
    elif pathway["method"] == "PathwayPredictor+OptGene":
        for gene_id in targets:
            for t in targets[gene_id]:
                gene_data = {"gene_target": gene_id}
                gene_data["gene_name"] = t["name"]
                gene_data["reaction_id"] = t["reaction_id"]
                gene_data["reaction_name"] = t["reaction_name"]
                gene_data["subsystem"] = t["subsystem"]
                gene_data["gpr"] = t["gpr"]
                gene_data["desinition_of_stoichiometry"] = t[
                    "desinition_of_stoichiometry"
                ]
                result.append(rxn_data)
        df = DataFrame(
            result,
            columns=[
                "gene_target",
                "gene_name",
                "reaction_id",
                "reaction_name",
                "subsystem",
                "gpr",
                "definition_of_stoichiometry",
            ],
        )
    elif pathway["method"] == "PathwayPredictor+CofactorSwap":
        for t in manipulations:
            rxn_id = t["id"]
            rxn_data = {"reaction_target": rxn_id}
            swapped_from = t["from"]
            swapped_to = t["to"]
            rxn_data["swapped_cofactors"] = "; ".join(
                [
                    swapped_from[i] + " -> " + swapped_to[i]
                    for i in range(len(swapped_from))
                ]
            )
            rxn_data["reaction_name"] = targets[rxn_id]["name"]
            rxn_data["subsystem"] = targets[rxn_id]["subsystem"]
            rxn_data["gpr"] = targets[rxn_id]["gpr"]
            rxn_data["definition_of_stoichiometry"] = targets[rxn_id][
                "definition_of_stoichiometry"
            ]
            result.append(rxn_data)
        df = DataFrame(
            result,
            columns=[
                "reaction_target",
                "reaction_name",
                "swapped_cofactors",
                "subsystem",
                "gpr",
                "definition_of_stoichiometry",
            ],
        )
    else:
        raise ValueError(f"Unknown method '{pathway.method}'.")
    return df.to_csv()


def init_app(app):
    """Register API resources on the provided Flask application."""

    def register(path, resource):
        app.add_url_rule(path, view_func=resource.as_view(resource.__name__))
        docs.register(resource, endpoint=resource.__name__)

    docs = FlaskApiSpec(app)
    register("/predictions", PredictionJobsResource)
    register("/predictions/<string:job_id>", PredictionJobResource)
    register(
        "/predictions/<string:job_id>/<string:pathway_id>", PathwayResource
    )
    register("/products", ProductsResource)
