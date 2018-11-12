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

"""Readiness check endpoint."""

from flask import jsonify

from .models import db


def init_app(app):
    """Register the readiness check endpoint on the given app."""
    @app.route('/healthz')
    def healthz():
        """
        Run readiness checks.

        Failed checks are allowed to raise uncaught exceptions to be logged.
        """
        checks = []

        # Database ping
        db.session.execute('select version()').fetchall()
        checks.append({'name': "DB Connectivity", 'status': 'pass'})

        return jsonify(checks)
