#!/usr/bin/env bash

# Copyright 2018-2020 Novo Nordisk Foundation Center for Biosustainability, DTU.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -xeu

# Redeployment of metabolic-ninja requires threading a bit more carefully than normally,
# to make sure that workers stop and terminate before the RabbitMQ broker disconnects.
# First terminate the workers. Since the grace period is fairly short, they will likely
# get killed and not complete the jobs. RabbitMQ will note that workers with any
# unacknowledged messages have disconnected, and requeue those messages when workers
# come back up. Then soft redeploy the rabbitmq web pod as usual. Finally, redeploy the
# workers with the new version. Any existing jobs will be rescheduled and started from
# scratch.
if [ "${TRAVIS_BRANCH}" = "master" ]; then
  kubectl delete deployment metabolic-ninja-worker-production
  kubectl set image deployment/metabolic-ninja-production web=${IMAGE}:${BUILD_TAG}
  kubectl apply -f deployment/production/deployment.yml
elif [ "${TRAVIS_BRANCH}" = "devel" ]; then
  kubectl delete deployment metabolic-ninja-worker-staging
  kubectl set image deployment/metabolic-ninja-staging web=${IMAGE}:${BUILD_TAG}
  kubectl apply -f deployment/staging/deployment.yml
else
  echo "Skipping deployment for branch ${TRAVIS_BRANCH}"
  exit 0
fi
