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

import cameo.api
import logging

from .decorators import task
from .universal import UNIVERSAL_SOURCES


logger = logging.getLogger(__name__)


def design(job):
    """Run the metabolic ninja design workflow."""
    try:
        logger.debug(f"Initiating new design workflow")
        source = UNIVERSAL_SOURCES[(job.bigg, job.rhea)]
        product = find_product(job, source)
        pathways = find_pathways(job, product, source)
        # optimize(model)
        # concatenate()
        # persist()
        # notify()
    except Exception:
        # Exceptions are handled in the child processes, so there's nothing to do here.
        # Just abort the workflow and get ready for new jobs.
        pass


@task
def find_product(job, source):
    # Find the product name via the cameo designer. In a future far, far away
    # this should be a call to a web service.
    logger.debug("Task starting: Find product")
    # TODO: update db state
    return cameo.api.design.translate_product_to_universal_reactions_model_metabolite(
        job.product_name, source
    )
    logger.debug("Task finished: Find product")


@task
def find_pathways(job, product, source):
    logger.debug("Task starting: Find pathways")
    # TODO: update db state
    predictor = cameo.strain_design.pathway_prediction.PathwayPredictor(
        job.model, universal_model=source
    )
    return predictor.run(
        product,
        max_predictions=job.max_predictions,
        timeout=120,  # seconds
        silent=True,
    )
    logger.debug("Task starting: Find pathways")
