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

import functools
import json
import logging

import cameo.api
from cobra.io.dict import metabolite_to_dict, reaction_to_dict
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail, Personalization

from . import designer
from .data import Job
from .decorators import TaskFailedException, task


logger = logging.getLogger(__name__)


def design(connection, channel, delivery_tag, body, ack_message):
    """Run the metabolic ninja design workflow."""
    job = Job.deserialize(json.loads(body))

    try:
        job.save(status="STARTED")

        logger.info(f"Initiating new design workflow")

        logger.debug("Starting task: Find product")
        product = find_product(job)

        logger.debug("Starting task: Find pathways")
        pathways = find_pathways(job, product)

        optimization_results = {
            "diff_fva": [],
            "opt_gene": [],
            "cofactor_swap": [],
            "reactions": {},
            "metabolites": {},
            "target": pathways[0].product.id if len(pathways) else "",
        }

        for index, pathway in enumerate(pathways, start=1):
            # Differential FVA
            logger.debug(
                f"Starting task: Differential FVA "
                f"(pathway {index}/{len(pathways)})"
            )
            results = diff_fva(job, pathway, "PathwayPredictor+DifferentialFVA")
            _collect_results(
                results,
                optimization_results["reactions"],
                optimization_results["metabolites"],
                optimization_results["diff_fva"],
            )

            # OptGene
            # FIXME (Moritz): Disabled for fast test on staging.
            # logger.debug(f"Starting task: OptGene
            # (pathway {index}/{len(pathways)})")
            # results = opt_gene(job, pathway, "PathwayPredictor+OptGene")
            # _collect_results(
            #     results,
            #     optimization_results["reactions"],
            #     optimization_results["metabolites"],
            #     optimization_results["opt_gene"],
            # )

            # Cofactor Swap Optimization
            logger.debug(
                f"Starting task: Cofactor Swap "
                f"(pathway {index}/{len(pathways)})"
            )
            results = cofactor_swap(
                job, pathway, "PathwayPredictor+CofactorSwap"
            )
            _collect_results(
                results,
                optimization_results["reactions"],
                optimization_results["metabolites"],
                optimization_results["cofactor_swap"],
            )

        # Save the results
        job.save(status="SUCCESS", result=optimization_results)

        _notify(job)
    except TaskFailedException:
        # Exceptions are handled in the child processes, so there's nothing to
        # do here. Just abort the workflow and get ready for new jobs.
        logger.info(
            f"Task failed; aborting workflow and restarting consumption from "
            f"queue."
        )
    finally:
        # Acknowledge the message, whether it failed or not.
        connection.add_callback_threadsafe(
            functools.partial(ack_message, channel, delivery_tag)
        )


@task
def find_product(job):
    # Find the product name via the cameo designer. In a future far, far away
    # this should be a call to a web service.
    return cameo.api.design.translate_product_to_universal_reactions_model_metabolite(  # noqa: E501
        job.product_name, job.source
    )


@task
def find_pathways(job, product):
    predictor = cameo.strain_design.pathway_prediction.PathwayPredictor(
        job.model, universal_model=job.source
    )
    return predictor.run(
        product,
        max_predictions=job.max_predictions,
        timeout=120,  # seconds
        silent=True,
    )


@task
def diff_fva(job, pathway, method):
    logger.debug("DiffFVA: Optimizing")
    designs = designer.differential_fva_optimization(pathway, job.model)
    logger.debug("DiffFVA: Evaluating")
    results = designer.evaluate_diff_fva(designs, pathway, job.model, method)
    # TODO (Moritz Beber): We disable the evaluation of exotic co-factors for
    #  now. As there is an unresolved bug that will get in the way of the user
    #  optimizeview.
    # results = designer.evaluate_exotic_cofactors(results, pathway, job.model)
    return results


@task
def opt_gene(job, pathway, method):
    logger.debug("OptGene: Optimizing")
    designs = designer.opt_gene(pathway, job.model)
    logger.debug("OptGene: Evaluating")
    results = designer.evaluate_opt_gene(designs, pathway, job.model, method)
    # TODO (Moritz Beber): We disable the evaluation of exotic co-factors for
    #  now. As there is an unresolved bug that will get in the way of the user
    #  optimizeview.
    # results = designer.evaluate_exotic_cofactors(results, pathway, job.model)
    return results


@task
def cofactor_swap(job, pathway, method):
    logger.debug("Cofactor swap: Optimizing")
    designs = designer.cofactor_swap_optimization(pathway, job.model)
    logger.debug("Cofactor swap: Evaluating")
    results = designer.evaluate_cofactor_swap(
        designs, pathway, job.model, method
    )
    # TODO (Moritz Beber): We disable the evaluation of exotic co-factors for
    #  now. As there is an unresolved bug that will get in the way of the user
    #  optimizeview.
    # results = designer.evaluate_exotic_cofactors(results, pathway, job.model)
    return results


def _collect_results(results, reactions, metabolites, container):
    for row in results:
        # Move the full reaction and metabolite definitions in a dict keyed by
        # ID to avoid duplicate definitions.
        for reaction in row.get("heterologous_reactions", []):
            reactions[reaction.id] = reaction_to_dict(reaction)
            for metabolite in reaction.metabolites:
                metabolites[metabolite.id] = metabolite_to_dict(metabolite)
        for reaction in row.get("synthetic_reactions", []):
            reactions[reaction.id] = reaction_to_dict(reaction)
        for metabolite in row.get("exotic_cofactors", []):
            metabolites[metabolite.id] = metabolite_to_dict(metabolite)

        # Replace reaction/metabolite references with their IDs in the actual
        # results.
        row["knockouts"] = [t.id for t in row.get("knockouts", [])]
        row["manipulations"] = row.get("manipulations", [])
        row["heterologous_reactions"] = [
            r.id for r in row.get("heterologous_reactions", [])
        ]
        row["synthetic_reactions"] = [
            r.id for r in row.get("synthetic_reactions", [])
        ]
        row["exotic_cofactors"] = [
            m.id for m in row.get("exotic_cofactors", [])
        ]

        # Add the full result row to the appropriate container
        # (based on method).
        container.append(row)


def _notify(job):
    try:
        logger.debug(
            f"Sending email notification to {job.user_name} <{job.user_email}>"
        )
        sendgrid = SendGridAPIClient()
        mail = Mail()
        mail.from_email = Email("DD-DeCaF <notifications@dd-decaf.eu>")
        mail.template_id = "d-8caebf4f862b4c67932515c45c5404cc"
        personalization = Personalization()
        personalization.add_to(Email(job.user_email))
        personalization.dynamic_template_data = {
            "name": job.user_name,
            "product": job.product_name,
            "organism": job.organism_name,
            "results_url": f"https://caffeine.dd-decaf.eu/jobs/{job.job_id}",
        }
        mail.add_personalization(personalization)
        sendgrid.client.mail.send.post(request_body=mail.get())
    except Exception as error:
        # Suppress any problem so it doesn't mark the entire workflow as failed,
        # but do log a warning for potential follow-up.
        logger.warning(
            "Unable to send email notification upon job completion",
            exc_info=error,
        )
