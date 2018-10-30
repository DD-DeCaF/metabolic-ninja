# Copyright 2018 Novo Nordisk Foundation Center for Biosustainability, DTU.
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

FROM gcr.io/dd-decaf-cfbf6/modeling-base:master

ARG CWD="/app"
ENV PYTHONPATH="${CWD}/src"
WORKDIR "${CWD}"

# pin pip to 18.0 to avoid issue with cobra -> depinfo -> pipdeptree -> pip._internal.get_installed_distributions
RUN pip install pip==18.0

COPY requirements.in dev-requirements.in ./
RUN pip install --upgrade -r requirements.in -r dev-requirements.in

COPY . "${CWD}/"
