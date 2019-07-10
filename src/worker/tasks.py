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

from . import designer
from .data import Job
from .decorators import task


logger = logging.getLogger(__name__)


def design(connection, channel, delivery_tag, body, ack_message):
    """Run the metabolic ninja design workflow."""
    job = Job.deserialize(json.loads(body))

    try:
        logger.info(f"Initiating new design workflow")

        logger.debug("Starting task: Find product")
        product = find_product(job)
        logger.debug(f"Task finished; found product: {product}")

        logger.debug("Starting task: Find pathways")
        pathways = find_pathways(job, product)
        logger.debug(
            f"Task finished: Find pathways, found {len(pathways)} pathways"
        )

        logger.debug("Starting task: Optimize")
        results = optimize(job, pathways)
        logger.debug("Task finished: Optimize")

        # persist()
        # notify()
    except Exception:
        # Exceptions are handled in the child processes, so there's nothing to do here.
        # Just abort the workflow and get ready for new jobs.
        logger.info(
            f"Task failed; aborting workflow and restaring consumption from queue"
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
    # TODO: update db state
    return cameo.api.design.translate_product_to_universal_reactions_model_metabolite(
        job.product_name, job.source
    )


@task
def find_pathways(job, product):
    # TODO: update db state
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
def optimize(job, pathways):
    reactions = {}
    metabolites = {}
    diff_fva = []
    opt_gene = []
    cofactor_swap = []

    for pathway in pathways:
        # TODO (Moritz Beber): We disable the evaluation of exotic co-factors for
        #  now. As there is an unresolved bug that will get in the way of the user
        #  review.

        # Differential FVA
        logger.debug("Starting optimization with Differential FVA")
        designs = designer.differential_fva_optimization(pathway, job.model)
        results = designer.evaluate_diff_fva(
            designs, pathway, job.model, "PathwayPredictor+DifferentialFVA"
        )
        # results = designer.evaluate_exotic_cofactors(results, pathway, job.model)
        _collect_results(results, reactions, metabolites, diff_fva)

        # OptGene
        # FIXME (Moritz): Disabled for fast test on staging.
        # logger.debug("Starting optimization with OptGene")
        # designs = designer.opt_gene(pathway, job.model)
        # results = designer.evaluate_opt_gene(designs, pathway, job.model, "PathwayPredictor+OptGene")
        # results = designer.evaluate_exotic_cofactors(results, pathway, job.model)
        # _collect_results(results, reactions, metabolites, opt_gene)

        # Cofactor Swap Optimization
        logger.debug("Starting optimization with Cofactor Swapping")
        designs = designer.cofactor_swap_optimization(pathway, job.model)
        results = designer.evaluate_cofactor_swap(
            designs, pathway, job.model, "PathwayPredictor+CofactorSwap"
        )
        # results = designer.evaluate_exotic_cofactors(results, pathway, job.model)
        _collect_results(results, reactions, metabolites, cofactor_swap)

    return {
        "diff_fva": diff_fva,
        "cofactor_swap": cofactor_swap,
        "opt_gene": opt_gene,
        "reactions": reactions,
        "metabolites": metabolites,
    }


def _collect_results(results, reactions, metabolites, container):
    for row in results:
        for reaction in row.get("heterologous_reactions", []):
            reactions[reaction.id] = reaction_to_dict(reaction)
            for metabolite in reaction.metabolites:
                metabolites[metabolite.id] = metabolite_to_dict(metabolite)
        for reaction in row.get("synthetic_reactions", []):
            reactions[reaction.id] = reaction_to_dict(reaction)
        for metabolite in row.get("exotic_cofactors", []):
            metabolites[metabolite.id] = metabolite_to_dict(metabolite)

        container.append(
            {
                "method": row["method"],
                "knockouts": [t.id for t in row.get("knockouts", [])],
                "manipulations": row.get("manipulations", []),
                "heterologous_reactions": [
                    r.id for r in row.get("heterologous_reactions", [])
                ],
                "synthetic_reactions": [
                    r.id for r in row.get("synthetic_reactions", [])
                ],
                "exotic_cofactors": [
                    m.id for m in row.get("exotic_cofactors", [])
                ],
            }
        )
