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

from cameo.models import universal


logger = logging.getLogger(__name__)


UNIVERSAL_SOURCES = {
    (True, False): universal.metanetx_universal_model_bigg,
    (True, True): universal.metanetx_universal_model_bigg_rhea,
    (False, True): universal.metanetx_universal_model_rhea,
}


# We explicitly access the models in order to pre-load them.
for db in UNIVERSAL_SOURCES.values():
    logger.debug("%s: %d reactions and %d metabolites.",
                 db.id, len(db.reactions), len(db.metabolites))
