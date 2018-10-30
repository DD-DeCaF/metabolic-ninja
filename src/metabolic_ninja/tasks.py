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

from cameo import models
from cameo.strain_design import pathway_prediction
from cobra.io.dict import reaction_to_dict

from .celery import celery_app


@celery_app.task
def predict(model_name, product_name, max_predictions):
    model = getattr(models.bigg, model_name)
    predictor = pathway_prediction.PathwayPredictor(model)
    pathways = predictor.run(product=product_name, max_predictions=max_predictions)
    # Proof of concept implementation: Return the reaction identifiers
    return [[reaction_to_dict(r) for r in p.reactions] for p in pathways.pathways]
