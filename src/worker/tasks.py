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

from .decorators import fork


logger = logging.getLogger(__name__)


def design(job):
    """Run the metabolic ninja design workflow."""
    try:
        find_product(product_name)
        # find_pathways()
        # optimize(model)
        # concatenate()
        # persist()
        # notify()
    except Exception as exception:
        # TODO: sentry
        # TODO: update db state
        logger.exception(exception)


@fork
def find_product(product_name):
    # TODO: update db state
    pass
