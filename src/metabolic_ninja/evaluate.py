# Copyright 2019 Novo Nordisk Foundation Center for Biosustainability,
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


"""Evaluate production levels and yields."""


import logging
from typing import Optional, Tuple

import cobra
from cameo.strain_design.heuristic.evolutionary.objective_functions import (
    biomass_product_coupled_min_yield,
    biomass_product_coupled_yield,
    product_yield,
)
from cobra.exceptions import OptimizationError
from cobra.flux_analysis import pfba
from cobra.flux_analysis.phenotype_phase_plane import (
    reaction_elements,
    reaction_weight,
    total_yield,
)
from numpy import isnan


__all__ = ("evaluate_production", "evaluate_biomass_coupled_production")


logger = logging.getLogger(__name__)


def evaluate_production(
    model: cobra.Model, production_id: str, carbon_source_id: str
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Evaluate the production levels in the specific model conditions.

    Warnings
    --------
    This function is expected to be called within a context since it modifies
    the model's objective.

    Parameters
    ----------
    model : cobra.Model
        The constraint-based metabolic model of the production organism.
    production_id : str
        The identifier of the reaction representing production, for example,
        a demand reaction on the compound.
    carbon_source_id : str
        The identifier of the reaction representing carbon uptake, for example,
        a glucose exchange reaction.

    Returns
    -------
    tuple
        float or None
            The theoretical maximum production rate if any.
        float or None
            The maximal product flux yield if any.
        float or None
            The maximal product carbon yield if any.
        float or None
            The maximal product yield by weight if any.

    """
    pyield = product_yield(production_id, carbon_source_id)
    # Compute the number of weighted carbon atoms.
    carbon_uptake = model.reactions.get_by_id(carbon_source_id)
    production = model.reactions.get_by_id(production_id)
    input_components = [reaction_elements(carbon_uptake)]
    output_components = reaction_elements(production)
    # Compute the masses.
    try:
        input_weights = [reaction_weight(carbon_uptake)]
        output_weight = reaction_weight(production)
    # If the reactions are ill-defined or the metabolite weight is unknown.
    except (ValueError, TypeError):
        input_weights = []
        output_weight = []
    try:
        model.objective = production_id
        solution = model.optimize()
        production_flux = solution[production_id]
    except OptimizationError as error:
        logger.error(
            "Could not determine production due to a solver error. %r", error
        )
        production_flux = None
        production_flux_yield = None
        production_carbon_yield = None
        production_mass_yield = None
    else:
        try:
            production_flux_yield = pyield(model, solution, None)
        except ZeroDivisionError:
            logger.error("Division by zero in yield calculation.")
            production_flux_yield = None
        production_carbon_yield = total_yield(
            [solution[carbon_source_id]],
            input_components,
            solution[production_id],
            output_components,
        )
        if isnan(production_carbon_yield):
            production_carbon_yield = None
        production_mass_yield = total_yield(
            [solution[carbon_source_id]],
            input_weights,
            solution[production_id],
            output_weight,
        )
        if isnan(production_mass_yield):
            production_mass_yield = None

    return (
        production_flux,
        production_flux_yield,
        production_carbon_yield,
        production_mass_yield,
    )


def evaluate_biomass_coupled_production(
    model: cobra.Model,
    production_id: str,
    biomass_id: str,
    carbon_source_id: str,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Evaluate the biomass coupled production levels in the specific conditions.

    Warnings
    --------
    This function is expected to be called within a context since it modifies
    the model's objective.

    Parameters
    ----------
    model : cobra.Model
        The constraint-based metabolic model of the production organism.
    production_id : str
        The identifier of the reaction representing production, for example,
        a demand reaction on the compound.
    biomass_id : str
        The identifier of the reaction representing biomass accumulation, i.e.,
        growth.
    carbon_source_id : str
        The identifier of the reaction representing carbon uptake, for example,
        a glucose exchange reaction.

    Returns
    -------
    tuple
        float or None
            The theoretical maximum growth rate if any.
        float or None
            The maximum biomass coupled product yield if any.
        float or None
            The maximal biomass coupled minimal product yield if any.

    """
    bpcy = biomass_product_coupled_yield(
        biomass_id, production_id, carbon_source_id
    )
    bpcmy = biomass_product_coupled_min_yield(
        biomass_id, production_id, carbon_source_id
    )
    try:
        model.objective = biomass_id
        solution = pfba(model)
        growth = solution[biomass_id]
    except OptimizationError as error:
        logger.error(
            "Could not determine biomass coupled production due to a solver "
            "error. %r",
            error,
        )
        growth = None
        bpc_yield = None
        bpcm_yield = None
    else:
        try:
            bpc_yield = bpcy(model, solution, None)
            bpcm_yield = bpcmy(model, solution, None)
        except ZeroDivisionError:
            logger.error("Division by zero in yield calculation.")
            bpc_yield = None
            bpcm_yield = None
    return growth, bpc_yield, bpcm_yield
