#!/usr/bin/env bash

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

set -xeu

if [ "${TRAVIS_BRANCH}" = "master" ]; then
  kubectl set image deployment/metabolic-ninja-production web=${IMAGE_REPO}:${TRAVIS_COMMIT::12}
elif [ "${TRAVIS_BRANCH}" = "devel" ]; then
  # Redeployment of metabolic-ninja requires threading a bit more carefully than
  # normally.

  # First disconnect and take down the workers completely. This way, rabbitmq will note
  # that workers with any unacknowledged messages (meaning jobs in progress) have
  # disconnected and will requeue those messages when workers come back up.
  kubectl delete deployment metabolic-ninja-worker-staging

  # Now soft redeploy the web + rabbitmq pod.
  kubectl set image deployment/metabolic-ninja-staging web=${IMAGE_REPO}:${TRAVIS_COMMIT::12}

  # Finally, redeploy the workers with the new version. RabbitMQ will resend any aborted
  # jobs. They'll have to be restarted from scratch, but will at least not become stale.
  kubectl apply -Rf deployment/staging/deployment.yml
else
  echo "Skipping deployment for branch ${TRAVIS_BRANCH}"
  exit 0
fi
