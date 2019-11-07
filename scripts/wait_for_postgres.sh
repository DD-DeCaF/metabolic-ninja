#!/usr/bin/env bash

# Copyright (c) 2018, Novo Nordisk Foundation Center for Biosustainability,
# Technical University of Denmark.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -eu

# Note: postgres will sporadically accept connections while the
# docker-entrypoint script is still running, so an explicit check for init to
# have finished is required in addition to the connection check.

echo "Waiting for postgres docker-entrypoint script to finish..."
while [[ ! "$(docker-compose logs --no-color postgres)" = *"PostgreSQL init process complete; ready for start up."* ]]; do
  sleep 1
done

echo "Waiting for postgres to accept connections..."
until docker-compose exec postgres psql -U postgres -l > /dev/null; do
  sleep 1
done
