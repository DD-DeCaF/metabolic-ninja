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

"""Marshmallow schemas for marshalling the API endpoints."""

from marshmallow import Schema, fields, post_load


class StrictSchema(Schema):
    """Shared empty schema instance with strict validation."""

    class Meta:
        """Meta class for marshmallow schemas."""

        strict = True


class PredictionJobRequestSchema(StrictSchema):
    model_id = fields.Integer(required=True)
    project_id = fields.Integer(required=False)
    product_name = fields.String(required=True)
    max_predictions = fields.Integer(required=True)


class JWTSchema(StrictSchema):
    token = fields.String(name="Authorization", required=False)

    # @post_load
    # def extract_token(self, data):
    #     # TODO: Error check supplied 'Authorization' value.
    #     return {
    #         "token": data.split(" ", 1)[1],
    #         "bearer": data
    #     }
