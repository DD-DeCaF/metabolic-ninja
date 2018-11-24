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
import re
from operator import itemgetter


__all__ = ("identify_exotic_cofactors",)


logger = logging.getLogger(__name__)
atom_pattern = re.compile(r"(?P<atom>[A-Z][a-z]?)(?P<count>[0-9]*)")


def count_atoms(formula):
    """Convert a formula string into a dictionary of counts."""
    return {
        m.group("atom"):
        1 if len(m.group("count")) == 0 else int(m.group("count"))
        for m in atom_pattern.finditer(formula)
    }


def compute_chemical_linkage_strength(counts_a, counts_d):
    """
    Compute the strength of chemical linkage (SCL) as in [1]_.

    Parameters
    ----------
    counts_a : dict
        A mapping between atoms as characters and their counts as parsed from a
        formula.
    counts_d : dict
        A mapping between atoms as characters and their counts as parsed from a
        formula.

    Returns
    -------
    float
        Return the strength of chemical linkage between compound A and B which
        is the 'intersection' between their atom counts, normalized by the
        greater of the total atom counts of either A or B.

    References
    ----------
    .. [1] Zhou, Wanding and Luay, Nakhleh.
       "The Strength of Chemical Linkage as a Criterion for Pruning Metabolic
       Graphs." Bioinformatics 27, no. 14 (July 15, 2011): 1957–63.
       https://doi.org/10.1093/bioinformatics/btr271.

    """
    scl = 0
    a_total = 0
    d_total = 0
    atoms = counts_a.keys() | counts_d.keys()
    # Ignoring hydrogen atoms is a heuristic from the original publication.
    if "H" in atoms:
        atoms.remove("H")
    for atom in atoms:
        a_freq = counts_a.get(atom, 0)
        d_freq = counts_d.get(atom, 0)
        a_total += a_freq
        d_total += d_freq
        scl += min(a_freq, d_freq)
    return scl / max(a_total, d_total)


def identify_exotic_cofactors(pathway, model, threshold=1E-07):
    """
    Take a heterologous pathway and identify all non-native co-factors.

    Parameters
    ----------
    pathway : cameo.strain_design.pathway_prediction.pathway_predictor.PathwayResult
        One of the predicted heterologous pathways predicted by cameo.
    model : cobra.Model
        The model to which the pathway should be added.
    threshold : float, optional
        The threshold for regarding fluxes as zero. Should be set to the
        solver tolerance.

    Returns
    -------
    list
        All the candidate exotic (non-native) co-factors.

    Raises
    ------
    OptimizationError
        If producing the heterologous product with the given model is
        infeasible.

    Warnings
    --------
    The current design is only meant for linear pathways. It will likely be
    incorrect for branching ones.

    """
    # Find the direction of flux through the pathway to the product.
    with model:
        pathway.apply(model)
        model.objective = model.reactions.get_by_id(pathway.product.id)
        model.objective_direction = "max"
        solution = model.optimize()
    # Adapters are single compound reactions: native <=> heterologous.
    adapted_sources = frozenset([r.products[0] for r in pathway.adapters])
    heterologous_reactions = frozenset(pathway.reactions)
    # The pathway `product` is a demand reaction.
    target = pathway.product.reactants[0]
    atom_counts = {
        target: count_atoms(target.formula)
    }
    # We are interested in co-factors of real heterologous reactions only, i.e.,
    # not adapters nor exchanges.
    rxn_queue = list(target.reactions & heterologous_reactions)
    seen = set()
    exotic_cofactors = set()
    while len(rxn_queue) > 0:
        rxn = rxn_queue.pop()
        seen.add(rxn)
        flux = 0.0 if abs(solution[rxn.id]) <= threshold else solution[rxn.id]
        if flux > 0:
            substrates = set(rxn.reactants)
            products = set(rxn.products)
        elif flux < 0:
            substrates = set(rxn.products)
            products = set(rxn.reactants)
        else:
            logger.warning("No flux through heterologous reaction %r!",
                           rxn.id)
            continue
        products.remove(target)
        exotic_cofactors.update(products - adapted_sources)
        # With one precursor, there is no doubt that it is not a co-factor.
        if len(substrates) == 1:
            target = substrates.pop()
            rxn_queue.extend((target.reactions & heterologous_reactions) - seen)
            continue
        # With multiple precursors, we evaluate the strength of chemical
        # linkage in order to weed out co-factors.
        options = []
        for compound in substrates:
            # Generate the atom counts from the formulae.
            count = atom_counts.setdefault(compound,
                                           count_atoms(compound.formula))
            target_count = atom_counts.setdefault(target,
                                                  count_atoms(target.formula))
            scl = compute_chemical_linkage_strength(
                count, target_count)
            options.append((compound, scl))
        # The maximum SCL is our candidate precursor.
        options.sort(key=itemgetter(1))
        logger.debug("Target: %r", target.id)
        logger.debug("Precursor options: %r", options)
        target, scl = options.pop()
        logger.info("Picking %r (%r) with SCL = %.3G.", target.id,
                    target.name, scl)
        # All other precursors are potentially non-native co-factors.
        exotic_cofactors.update(
            set(o[0] for o in options) - adapted_sources
        )
        # Add new reactions to exploration queue.
        rxn_queue.extend((target.reactions & heterologous_reactions) - seen)
    return exotic_cofactors
