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

"""Test expected functioning of the OpenAPI docs endpoints."""


import pytest

from metabolic_ninja.models import DesignJob


def test_docs(client):
    """Expect the OpenAPI docs to be served at root."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.content_type == "text/html; charset=utf-8"


def test_get_predictions(client, session):
    """"""
    # Create some jobs.
    job_1 = DesignJob(organism_id=1, model_id=2, product_name='vanillin', max_predictions=6, status="PENDING")
    job_2 = DesignJob(organism_id=3, model_id=4, product_name='vanillin', max_predictions=3, status="PENDING")
    session.add(job_1)
    session.add(job_2)
    session.commit()
    expected = {j.id: j for j in [job_1, job_2]}
    response = client.get("/predictions")
    assert response.status_code == 200
    assert response.content_type == "application/json"
    data = response.get_json(cache=False)
    assert len(data) == 2
    for job in data:
        expect = expected[job["id"]]
        assert job["organism_id"] == expect.organism_id
        assert job["model_id"] == expect.model_id
        assert job["status"] == expect.status
        assert job["product_name"] == expect.product_name
        assert job["max_predictions"] == expect.max_predictions
        assert job["created"] == expect.created.isoformat()


@pytest.mark.parametrize("status, code", [
    ("PENDING", 202),
    ("STARTED", 202),
    ("SUCCESS", 200),
    ("FAILURE", 200),
    ("REVOKED", 200),
])
def test_get_single_prediction(client, session, status, code):
    """"""
    # Create some jobs.
    expect = DesignJob(organism_id=1, model_id=2, product_name='vanillin', max_predictions=6, status=status)
    session.add(expect)
    session.commit()
    response = client.get(f"/predictions/{expect.id}")
    assert response.status_code == code
    assert response.content_type == "application/json"
    job = response.get_json(cache=False)
    assert job["id"] == expect.id
    assert job["organism_id"] == expect.organism_id
    assert job["model_id"] == expect.model_id
    assert job["product_name"] == expect.product_name
    assert job["max_predictions"] == expect.max_predictions
    assert job["status"] == expect.status
    assert job["created"] == expect.created.isoformat()
