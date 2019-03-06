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

"""Expose the main Flask application."""

import logging
import logging.config

import sentry_sdk
from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from sentry_sdk.integrations.flask import FlaskIntegration

from werkzeug.contrib.fixers import ProxyFix

from . import jwt


app = Flask(__name__)


def init_app(application, database):
    """Initialize the main app with config information and routes."""
    from metabolic_ninja.settings import current_config
    application.config.from_object(current_config())

    # Configure logging
    logging.config.dictConfig(application.config['LOGGING'])

    # Configure the database connection.
    database.init_app(application)
    Migrate(application, database)

    # Add middleware.
    jwt.init_app(application)

    # Configure Sentry
    if application.config['SENTRY_DSN']:
        sentry_sdk.init(
            dsn=application.config['SENTRY_DSN'],
            integrations=[FlaskIntegration()],
        )

    # Add routes and resources.
    from metabolic_ninja import resources
    resources.init_app(application)

    # Add CORS information for all resources.
    CORS(application)

    # Add readiness check endpoint
    from . import healthz
    healthz.init_app(application)

    # Add an error handler for webargs parser error, ensuring a JSON response
    # including all error messages produced from the parser.
    @app.errorhandler(422)
    def handle_webargs_error(error):
        response = jsonify(error.data['messages'])
        response.status_code = error.code
        return response

    # Please keep in mind that it is a security issue to use such a middleware
    # in a non-proxy setup because it will blindly trust the incoming headers
    # which might be forged by malicious clients.
    # We require this in order to serve the HTML version of the OpenAPI docs
    # via https.
    application.wsgi_app = ProxyFix(application.wsgi_app)
