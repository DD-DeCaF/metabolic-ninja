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

import logging
from uuid import uuid4

import cameo.core.target
from cameo.strain_design import DifferentialFVA, OptGene
from cameo.strain_design.heuristic.evolutionary.objective_functions import (
    biomass_product_coupled_min_yield,
    product_yield,
)
from cameo.strain_design.heuristic.evolutionary_based import CofactorSwapOptimization
from cobra.exceptions import OptimizationError
from numpy import isnan

from .evaluate import evaluate_biomass_coupled_production, evaluate_production
from .helpers import find_synthetic_reactions, manipulation_helper


logger = logging.getLogger(__name__)


def differential_fva_optimization(pathway, model):
    """
    Compare FVA results on the production plane with maximum growth.

    Parameters
    ----------
    pathway :
        A heterologous pathway identified by cameo.
    model : cobra.Model
        The model under investigation.

    Returns
    -------
    cameo.design
        A number of differential FVA designs corresponding to evenly spaced
        points on the surface of the phenotypic phase plane.

    """
    with model:
        pathway.apply(model)
        predictor = DifferentialFVA(
            design_space_model=model,
            objective=pathway.product.id,
            variables=[model.biomass],
            normalize_ranges_by=model.biomass,
            # Excluding the maxima, this corresponds to three evenly spaced
            # designs.
            points=5,
        )
        try:
            designs = predictor.run(progress=False)
        except ZeroDivisionError as error:
            logger.warning(
                "Encountered the following error in DiffFVA.", exc_info=error
            )
            designs = None
    return designs


def evaluate_diff_fva(designs, pathway, model, method):
    """Evaluate the differential FVA designs."""
    if designs is None:
        return []
    logger.info(
        f"Evaluating {len(designs) - 1} differential FVA surface points."
    )
    table = designs.nth_panel(0)
    results = []
    designs = list(designs)
    with model:
        pathway.apply(model)
        # The reference point is automatically ignored. Thus four of the
        # original five points remain. The first point in order represents
        # maximum production and zero growth. We ignore the point of lowest
        # production (the last one in order).
        reaction_targets = {}
        for design_result in designs[:-1]:
            with model:
                design_result.apply(model)
                with model:
                    production, _, carbon_yield, _ = evaluate_production(
                        model, pathway.product.id, model.carbon_source
                    )
                with model:
                    growth, bpcy = evaluate_biomass_coupled_production(
                        model,
                        pathway.product.id,
                        model.biomass,
                        model.carbon_source,
                    )
            knockouts = {
                r
                for r in design_result.targets
                if isinstance(r, cameo.core.target.ReactionKnockoutTarget)
            }
            manipulations = [
                manipulation_helper(t)
                for t in set(design_result.targets).difference(knockouts)
            ]
            reaction_targets.update(
                get_target_data(model, table, manipulations, False)
            )
            reaction_targets.update(
                get_target_data(model, table, list(knockouts), True)
            )
            results.append(
                {
                    "id": str(uuid4()),
                    "knockouts": list(knockouts),
                    "manipulations": manipulations,
                    "heterologous_reactions": pathway.reactions,
                    "synthetic_reactions": find_synthetic_reactions(pathway),
                    "fitness": bpcy,
                    "yield": carbon_yield,
                    "product": production,
                    "biomass": growth,
                    "method": method,
                    "targets": reaction_targets,
                }
            )
    return results


def opt_gene(pathway, model):
    with model:
        pathway.apply(model)
        predictor = OptGene(model=model, plot=False)
        designs = predictor.run(
            target=pathway.product.id,
            biomass=model.biomass,
            substrate=model.carbon_source,
            max_evaluations=int(1e06),
            max_knockouts=5,
            max_time=(2, 0, 0),  # (hours, minutes, seconds)
        )
    return designs


def evaluate_opt_gene(designs, pathway, model, method):
    if designs is None:
        return []
    logger.info(f"Evaluating {len(designs)} OptGene designs.")
    pyield = product_yield(pathway.product, model.carbon_source)
    bpcy = biomass_product_coupled_min_yield(
        model.biomass, pathway.product, model.carbon_source
    )
    results = []
    with model:
        pathway.apply(model)
        for design_result in designs:
            with model:
                design_result.apply(model)
                try:
                    model.objective = model.biomass
                    solution = model.optimize()
                    p_yield = pyield(model, solution, pathway.product)
                    bpc_yield = bpcy(model, solution, pathway.product)
                    target_flux = solution[pathway.product.id]
                    biomass = solution[model.biomass]
                except (OptimizationError, ZeroDivisionError):
                    p_yield = None
                    bpc_yield = None
                    target_flux = None
                    biomass = None
                else:
                    if isnan(p_yield):
                        p_yield = None
                    if isnan(bpc_yield):
                        bpc_yield = None
                    if isnan(target_flux):
                        target_flux = None
                    if isnan(biomass):
                        biomass = None
                knockouts = {
                    g
                    for g in design_result.targets
                    if isinstance(g, cameo.core.target.GeneKnockoutTarget)
                }
                gene_targets = {}
                for target in knockouts:
                    gene_id = target.id
                    gene = model.genes.get_by_id(gene_id)
                    gene_targets[gene_id] = []
                    for reaction_target in gene.reactions:
                        rxn_id = reaction_target.id
                        rxn = model.reactions.get_by_id(rxn_id)
                        gene_targets[gene_id].append(
                            {
                                "name": gene.name,
                                "reaction_id": rxn_id,
                                "reaction_name": rxn.name,
                                "subsystem": rxn.subsystem,
                                "gpr": rxn.gene_reaction_rule,
                                "definition_of_stoichiometry":
                                    rxn.build_reaction_string(True),
                            }
                        )
                results.append(
                    {
                        "id": str(uuid4()),
                        "knockouts": list(knockouts),
                        "heterologous_reactions": pathway.reactions,
                        "synthetic_reactions": find_synthetic_reactions(
                            pathway
                        ),
                        "fitness": bpc_yield,
                        "yield": p_yield,
                        "product": target_flux,
                        "biomass": biomass,
                        "method": method,
                        "targets": gene_targets,
                    }
                )
    return results


def cofactor_swap_optimization(pathway, model):
    with model:
        model.objective = model.biomass
        growth = model.slim_optimize()
    model.reactions.get_by_id(model.biomass).lower_bound = 0.05 * growth
    pathway.apply(model)
    model.objective = pathway.product.id
    pyield = product_yield(pathway.product.id, model.carbon_source)
    with model:
        # TODO (Moritz Beber): By default swaps NADH with NADPH using BiGG
        #  notation.
        predictor = CofactorSwapOptimization(
            model=model, objective_function=pyield, plot=False
        )
        designs = predictor.run(max_size=5, diversify=True)
    return designs


def evaluate_cofactor_swap(designs, pathway, model, method):
    if designs is None:
        return []
    logger.info(f"Evaluating {len(designs)} co-factor swap designs.")
    source_pair = ("nad_c", "nadh_c")
    target_pair = ("nadp_c", "nadph_c")
    results = []
    for design in designs.data_frame.itertuples(index=False):
        manipulations = []
        # FIXME (Moritz Beber): The model context is currently bugged.
        #  See https://github.com/opencobra/cobrapy/issues/849
        #  We need to make a copy.
        model_tmp = model.copy()
        source_a = model_tmp.metabolites.get_by_id(source_pair[0])
        source_b = model_tmp.metabolites.get_by_id(source_pair[1])
        target_a = model_tmp.metabolites.get_by_id(target_pair[0])
        target_b = model_tmp.metabolites.get_by_id(target_pair[1])
        reaction_targets = {}
        for rxn_id in design.targets:
            rxn = model_tmp.reactions.get_by_id(rxn_id)
            reaction_targets[rxn_id] = {
                "name": rxn.name,
                "subsystem": rxn.subsystem,
                "gpr": rxn.gene_reaction_rule,
                "definition_of_stoichiometry": rxn.build_reaction_string(True),
            }
            metabolites = rxn.metabolites
            # Swap from source to target co-factors.
            if source_a in metabolites:
                metabolites[target_a] = metabolites[source_a]
                metabolites[target_b] = metabolites[source_b]
                metabolites[source_a] = 0
                metabolites[source_b] = 0
                manipulations.append(
                    {"id": rxn_id, "from": source_pair, "to": target_pair}
                )
            elif target_a in metabolites:
                metabolites[source_a] = metabolites[target_a]
                metabolites[source_b] = metabolites[target_b]
                metabolites[target_a] = 0
                metabolites[target_b] = 0
                manipulations.append(
                    {"id": rxn_id, "from": target_pair, "to": source_pair}
                )
            else:
                raise KeyError(
                    f"Neither co-factor swap partner present in "
                    f"predicted target reaction '{rxn_id}'."
                )
            rxn.add_metabolites(metabolites, combine=False)
        logger.info("Calculating production values.")
        with model_tmp:
            prod_flux, _, prod_carbon_yield, _ = evaluate_production(
                model_tmp, pathway.product.id, model_tmp.carbon_source
            )
        logger.info("Calculating biomass coupled production values.")
        with model_tmp:
            growth, bpc_yield = evaluate_biomass_coupled_production(
                model_tmp,
                pathway.product.id,
                model_tmp.biomass,
                model_tmp.carbon_source,
            )
        results.append(
            {
                "id": str(uuid4()),
                "manipulations": manipulations,
                "heterologous_reactions": pathway.reactions,
                "synthetic_reactions": find_synthetic_reactions(pathway),
                "fitness": bpc_yield,
                "yield": prod_carbon_yield,
                "product": prod_flux,
                "biomass": growth,
                "method": method,
                "targets": reaction_targets,
            }
        )
    return results


def get_target_data(model, table, targets, knockout):
    result = {}
    for t in targets:
        rxn_id = t.id if knockout else t["id"]
        rxn = model.reactions.get_by_id(rxn_id)
        result[rxn_id] = {
            "name": rxn.name,
            "subsystem": rxn.subsystem,
            "gpr": rxn.gene_reaction_rule,
            "definition_of_stoichiometry": rxn.build_reaction_string(True),
            "flux_reversal": bool(table.at[rxn_id, "flux_reversal"]),
            "suddenly_essential": bool(table.at[rxn_id, "suddenly_essential"]),
            "knockout": knockout,
        }
    return result
