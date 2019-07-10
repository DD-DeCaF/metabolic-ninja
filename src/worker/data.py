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

import logging

import cobra.io

from .universal import UNIVERSAL_SOURCES


logger = logging.getLogger(__name__)


class Job:
    def __init__(
        self,
        model,
        product_name,
        max_predictions,
        aerobic,
        bigg,
        rhea,
        job_id,
        organism_id,
        organism_name,
        user_name,
        user_email,
    ):
        self.model = model
        self.product_name = product_name
        self.max_predictions = max_predictions
        self.aerobic = aerobic
        self.bigg = bigg
        self.rhea = rhea
        self.source = UNIVERSAL_SOURCES[(self.bigg, self.rhea)]
        self.job_id = job_id
        self.organism_id = organism_id
        self.organism_name = organism_name
        self.user_name = user_name
        self.user_email = user_email

    @staticmethod
    def deserialize(params):
        logger.debug("Deserializing job parameters")
        return Job(
            cobra.io.model_from_dict(params["model"]["model_serialized"]),
            params["product_name"],
            params["max_predictions"],
            params["aerobic"],
            params["bigg"],
            params["rhea"],
            params["job_id"],
            params["organism_id"],
            params["organism_name"],
            params["user_name"],
            params["user_email"],
        )
