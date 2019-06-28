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


import cobra
import pytest
from cameo.strain_design.pathway_prediction.pathway_predictor import (
    PathwayResult,
)

import metabolic_ninja.helpers as helpers


model_registry = {}
pathway_registry = {}


def register_with(registry):
    """Register a function."""

    def decorator(func):
        registry[func.__name__] = func
        return func

    return decorator


@pytest.fixture(scope="function")
def model(request):
    return model_registry[request.param]()


@pytest.fixture(scope="function")
def pathway(request):
    return pathway_registry[request.param]()


@register_with(model_registry)
def bare_mini():
    """Define a minimal metabolism with two metabolites."""
    model = cobra.Model()
    met_a = cobra.Metabolite("a_c", name="A", formula="C2")
    met_b = cobra.Metabolite("b_c", name="B", formula="C2")
    model.add_metabolites([met_a, met_b])
    rxn = cobra.Reaction("FORMB")
    rxn.add_metabolites({met_a: -1, met_b: 1})
    model.add_reactions([rxn])
    model.add_boundary(met_a)
    demand = model.add_boundary(met_b, type="demand")
    model.objective = demand
    model.objective_direction = "max"
    return model


@register_with(model_registry)
def mini_with_cofactors():
    """Define a minimal metabolism with two metabolites and co-factors."""
    model = cobra.Model()
    met_a = cobra.Metabolite("a_c", name="A", formula="C2")
    met_b = cobra.Metabolite("b_c", name="B", formula="C2")
    met_c = cobra.Metabolite("c_c", name="C", formula="O2")
    met_d = cobra.Metabolite("d_c", name="D", formula="CO")
    model.add_metabolites([met_a, met_b])
    rxn = cobra.Reaction("FORMB")
    rxn.add_metabolites({met_a: -1, met_b: 1})
    model.add_reactions([rxn])
    model.add_boundary(met_a)
    model.add_boundary(met_c)
    model.add_boundary(met_d)
    demand = model.add_boundary(met_b, type="demand")
    model.objective = demand
    model.objective_direction = "max"
    return model


@register_with(pathway_registry)
def straight_pathway():
    """Return a simple one-step heterologous pathway without co-factors."""
    met_b = cobra.Metabolite("b_c", name="B")
    met_b_prime = cobra.Metabolite("b_p_c", name="B'", formula="C2")
    met_p_prime = cobra.Metabolite("p_p_c", name="P'", formula="C2")
    rxn = cobra.Reaction("FORMP")
    rxn.add_metabolites({met_b_prime: -1, met_p_prime: 1})
    # Single production step heterologous pathway.
    reactions = [rxn]
    # Define drains for all heterologous metabolites.
    exchanges = []
    demand = cobra.Reaction(f"DM_{met_b_prime.id}")
    demand.add_metabolites({met_b_prime: -1})
    exchanges.append(demand)
    # Define adapter reactions between native and heterologous metabolites.
    adapter = cobra.Reaction(f"adapter_b_c_to_b_p_c")
    adapter.add_metabolites({met_b: -1, met_b_prime: 1})
    adapters = [adapter]
    product = cobra.Reaction(f"DM_{met_p_prime}")
    product.add_metabolites({met_p_prime: -1})
    return PathwayResult(reactions, exchanges, adapters, product)


@register_with(pathway_registry)
def straight_pathway_with_cofactors():
    """Return a simple one-step heterologous pathway with co-factors."""
    met_b = cobra.Metabolite("b_c", name="B")
    met_b_prime = cobra.Metabolite("b_p_c", name="B'", formula="C2")
    met_c_prime = cobra.Metabolite("c_p_c", name="C'", formula="O2")
    met_d_prime = cobra.Metabolite("d_p_c", name="D'", formula="CO")
    met_p_prime = cobra.Metabolite("p_p_c", name="P'", formula="C2O")
    rxn = cobra.Reaction("FORMP")
    rxn.add_metabolites(
        {met_b_prime: -1, met_c_prime: -1, met_d_prime: 1, met_p_prime: 1}
    )
    # Single production step heterologous pathway.
    reactions = [rxn]
    # Define drains for all heterologous metabolites.
    exchanges = []
    demand = cobra.Reaction(f"DM_{met_b_prime.id}")
    demand.add_metabolites({met_b_prime: -1})
    exchanges.append(demand)
    # Provide a source for C'.
    exchange = cobra.Reaction(f"EX_{met_c_prime.id}")
    exchange.add_metabolites({met_c_prime: -1})
    exchange.bounds = -10, 10
    exchanges.append(exchange)
    # Provide an exchange for D'.
    exchange = cobra.Reaction(f"EX_{met_d_prime.id}")
    exchange.add_metabolites({met_d_prime: -1})
    exchange.bounds = -10, 10
    exchanges.append(exchange)
    # Define adapter reactions between native and heterologous metabolites.
    adapter = cobra.Reaction(f"adapter_b_c_to_b_p_c")
    adapter.add_metabolites({met_b: -1, met_b_prime: 1})
    adapters = [adapter]
    product = cobra.Reaction(f"DM_{met_p_prime}")
    product.add_metabolites({met_p_prime: -1})
    return PathwayResult(reactions, exchanges, adapters, product)


@register_with(pathway_registry)
def straight_pathway_with_cofactors_and_adapters():
    """Return a simple one-step heterologous pathway with co-factors."""
    met_b = cobra.Metabolite("b_c", name="B")
    met_c = cobra.Metabolite("c_c", name="C")
    met_d = cobra.Metabolite("d_c", name="D")
    met_b_prime = cobra.Metabolite("b_p_c", name="B'", formula="C2")
    met_c_prime = cobra.Metabolite("c_p_c", name="C'", formula="O2")
    met_d_prime = cobra.Metabolite("d_p_c", name="D'", formula="CO")
    met_p_prime = cobra.Metabolite("p_p_c", name="P'", formula="C2O")
    rxn = cobra.Reaction("FORMP")
    rxn.add_metabolites(
        {met_b_prime: -1, met_c_prime: -1, met_d_prime: 1, met_p_prime: 1}
    )
    # Single production step heterologous pathway.
    reactions = [rxn]
    # Define drains for all heterologous metabolites.
    exchanges = []
    demand = cobra.Reaction(f"DM_{met_b_prime.id}")
    demand.add_metabolites({met_b_prime: -1})
    exchanges.append(demand)
    # Provide a source for C'.
    exchange = cobra.Reaction(f"EX_{met_c_prime.id}")
    exchange.add_metabolites({met_c_prime: -1})
    exchange.bounds = -10, 10
    exchanges.append(exchange)
    # Provide an exchange for D'.
    exchange = cobra.Reaction(f"EX_{met_d_prime.id}")
    exchange.add_metabolites({met_d_prime: -1})
    exchange.bounds = -10, 10
    exchanges.append(exchange)
    # Define adapter reactions between native and heterologous metabolites.
    adapters = []
    adapter = cobra.Reaction(f"adapter_b_c_to_b_p_c")
    adapter.add_metabolites({met_b: -1, met_b_prime: 1})
    adapters.append(adapter)
    adapter = cobra.Reaction(f"adapter_c_c_to_c_p_c")
    adapter.add_metabolites({met_c: -1, met_c_prime: 1})
    adapters.append(adapter)
    adapter = cobra.Reaction(f"adapter_d_c_to_d_p_c")
    adapter.add_metabolites({met_d: -1, met_d_prime: 1})
    adapters.append(adapter)
    product = cobra.Reaction(f"DM_{met_p_prime}")
    product.add_metabolites({met_p_prime: -1})
    return PathwayResult(reactions, exchanges, adapters, product)


@pytest.mark.parametrize(
    "formula, expected",
    [
        ("CHO", {"C": 1, "H": 1, "O": 1}),
        ("C2HO", {"C": 2, "H": 1, "O": 1}),
        ("CH3O", {"C": 1, "H": 3, "O": 1}),
        ("CHO4", {"C": 1, "H": 1, "O": 4}),
        ("C12HO", {"C": 12, "H": 1, "O": 1}),
        ("CoLi3Mn11", {"Co": 1, "Li": 3, "Mn": 11}),
    ],
)
def test_count_atoms(formula, expected):
    assert helpers.count_atoms(formula) == expected


@pytest.mark.parametrize(
    "counts_a, counts_d, expected_scl",
    [
        pytest.param(
            {}, {}, None, marks=pytest.mark.raises(exception=ZeroDivisionError)
        ),
        ({}, {"C": 1}, 0.0),
        ({"C": 1}, {}, 0.0),
        ({"C": 1}, {"C": 1}, 1.0),
        # Test that hydrogen does not influence the result.
        ({"H": 1}, {"C": 1, "H": 1}, 0.0),
        ({"C": 1, "H": 1}, {"H": 1}, 0.0),
        ({"C": 1}, {"C": 2}, 0.5),
        ({"C": 1}, {"C": 3}, 0.3),
        ({"C": 2}, {"C": 2, "O": 1}, 2 / 3),
        ({"O": 2}, {"C": 2, "O": 1}, 1 / 3),
        ({"C": 1, "O": 1}, {"C": 2, "O": 1}, 2 / 3),
    ],
)
def test_compute_chemical_linkage_strength(counts_a, counts_d, expected_scl):
    assert helpers.compute_chemical_linkage_strength(
        counts_a, counts_d
    ) == pytest.approx(expected_scl, rel=0.0, abs=0.1)


@pytest.mark.skip(
    reason="Evaluation of exotic cofactors is temporarily " "disabled"
)
@pytest.mark.parametrize(
    "model, pathway, exotic_cofactors",
    [
        ("bare_mini", "straight_pathway", set()),
        ("bare_mini", "straight_pathway_with_cofactors", {"c_p_c", "d_p_c"}),
        (
            "mini_with_cofactors",
            "straight_pathway_with_cofactors_and_adapters",
            set(),
        ),
    ],
    indirect=["model", "pathway"],
)
def test_identify_exotic_cofactors(model, pathway, exotic_cofactors):
    assert {
        m.id for m in helpers.identify_exotic_cofactors(pathway, model)
    } == exotic_cofactors
