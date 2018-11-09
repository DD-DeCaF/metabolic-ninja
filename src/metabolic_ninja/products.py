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

import cameo

from .universal import UNIVERSAL_SOURCES


logger = logging.getLogger(__name__)
_products = None


def products():
    if _products is None:
        _get_products()
    return _products


def _get_products():
    global _products
    logger.debug("Retrieving product list from cameo")
    _products = [
        {'name': m.name}
        for m in cameo.models.metanetx_universal_model_bigg_rhea.metabolites
    ]
    logger.debug(f"Cached {len(_products)} products")


if os.environ['ENVIRONMENT'] != 'development':
    _get_products()
