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

"""Test expected functioning of the helper functions."""


import pytest

import metabolic_ninja.helpers as helpers


@pytest.mark.parametrize("formula, expected", [
    ("CHO", {"C": 1, "H": 1, "O": 1}),
    ("C2HO", {"C": 2, "H": 1, "O": 1}),
    ("CH3O", {"C": 1, "H": 3, "O": 1}),
    ("CHO4", {"C": 1, "H": 1, "O": 4}),
    ("C12HO", {"C": 12, "H": 1, "O": 1}),
    ("CoLi3Mn11", {"Co": 1, "Li": 3, "Mn": 11}),
])
def test_count_atoms(formula, expected):
    assert helpers.count_atoms(formula) == expected


@pytest.mark.parametrize("counts_a, counts_d, expected_scl", [
    pytest.param({}, {}, None,
                 marks=pytest.mark.raises(exception=ZeroDivisionError)),
    ({}, {"C": 1}, 0.0),
    ({"C": 1}, {}, 0.0),
    ({"C": 1}, {"C": 1}, 1.0),
    # Test that hydrogen does not influence the result.
    ({"H": 1}, {"C": 1, "H": 1}, 0.0),
    ({"C": 1, "H": 1}, {"H": 1}, 0.0),
    ({"C": 1}, {"C": 2}, 0.5),
    ({"C": 1}, {"C": 3}, 0.3),
])
def test_compute_chemical_linkage_strength(counts_a, counts_d, expected_scl):
    assert helpers.compute_chemical_linkage_strength(
        counts_a, counts_d) == pytest.approx(expected_scl, rel=0.0, abs=0.1)
