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
import os
from contextlib import contextmanager

import cobra.io
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..models import DesignJob
from ..universal import UNIVERSAL_SOURCES


logger = logging.getLogger(__name__)


@contextmanager
def db_session():
    """Connect to the database and yield an SA session."""
    engine = create_engine(
        "postgresql://{POSTGRES_USERNAME}:{POSTGRES_PASS}@{POSTGRES_HOST}:"
        "{POSTGRES_PORT}/{POSTGRES_DB_NAME}".format(**os.environ)
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class Job:
    def __init__(
        self,
        model,
        biomass_reaction_id,
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
        # Configure the model object for cameo.
        self.model = model
        # FIXME (Moritz Beber): We should allow users to specify a medium that they
        #  previously
        # uploaded.
        self.model.solver = "cplex"
        # FIXME (Moritz Beber): This uses BiGG notation to change the lower bound
        #  of the exchange reaction. Should instead find this using a combination of
        #  metabolites in the `model.exchanges`, MetaNetX identifiers and/or
        #  metabolite formulae. Then set this on the `model.medium` to be sure
        #  about exchange direction.
        if not aerobic and "EX_o2_e" in self.model.reactions:
            self.model.reactions.EX_o2_e.lower_bound = 0
        self.model.biomass = biomass_reaction_id
        # FIXME (Moritz Beber): We can try to be smart, as in theoretical yield
        #  app, but ideally the carbon source is user defined just like
        #  default_biomass_reaction. Maybe we need a new field for the medium
        #  database model?
        self.model.carbon_source = "EX_glc__D_e"

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

    def save(self, **kwargs):
        logger.debug(f"Updating database status of job {self.job_id}")
        with db_session() as session:
            job = session.query(DesignJob).filter_by(id=self.job_id).one()
            for column, value in kwargs.items():
                setattr(job, column, value)
            session.add(job)
            session.commit()

    @staticmethod
    def deserialize(params):
        logger.debug("Deserializing job parameters")
        return Job(
            cobra.io.model_from_dict(params["model"]["model_serialized"]),
            params["model"]["default_biomass_reaction"],
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
