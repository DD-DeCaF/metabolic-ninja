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
# limitations under the License.from datetime import datetime


from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile

from flask_sqlalchemy import SQLAlchemy
from pandas import DataFrame, ExcelWriter
from sqlalchemy.dialects import postgresql


db = SQLAlchemy()


def tz_aware_now():
    return datetime.now(timezone.utc)


class TimestampMixin:

    created = db.Column(
        db.DateTime(timezone=True), nullable=False, default=tz_aware_now
    )
    updated = db.Column(
        db.DateTime(timezone=True), nullable=True, onupdate=tz_aware_now
    )


class DesignJob(TimestampMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=True, index=True)
    organism_id = db.Column(db.Integer, nullable=False)
    model_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String, nullable=False)
    max_predictions = db.Column(db.Integer, nullable=False)
    # Null is allowed to be compatible with the older jobs
    # created before the field existed
    aerobic = db.Column(db.Boolean, nullable=True)
    # The UUID assigned by celery.
    task_id = db.Column(db.String(36), nullable=True)
    # The status refers to
    # http://docs.celeryproject.org/en/latest/reference/celery.states.html#misc.
    status = db.Column(db.String(8), nullable=False)
    result = db.Column(postgresql.JSONB, nullable=True)

    def __repr__(self):
        """Return a printable representation."""
        return f"<{self.__class__.__name__} {self.id}>"

    def is_complete(self):
        return self.status in ("SUCCESS", "FAILURE", "REVOKED")

    def get_tabular_data(self, prediction):
        if prediction["method"] == "PathwayPredictor+DifferentialFVA":
            df = self.get_diff_fva_data(prediction)
        elif prediction["method"] == "PathwayPredictor+OptGene":
            df = self.get_opt_gene_data(prediction)
        elif prediction["method"] == "PathwayPredictor+CofactorSwap":
            df = self.get_cofactor_swap_data(prediction)
        else:
            raise ValueError(f"Unknown method '{prediction['method']}'.")
        memory_file = BytesIO()
        with ZipFile(memory_file, "w") as zf:
            zf.writestr("data.csv", df.to_csv())
            output = BytesIO()
            writer = ExcelWriter(output)
            df.to_excel(writer)
            writer.save()
            zf.writestr("data.xlsx", output.getvalue())
        return memory_file.getvalue()

    def get_diff_fva_data(self, prediction):
        result = []
        targets = prediction["targets"]
        manipulations = prediction["manipulations"]
        for target in manipulations:
            rxn_id = target["id"]

            rxn_data = {
                "reaction_target": rxn_id,
                "reaction_name": targets[rxn_id]["name"],
                "subsystem": targets[rxn_id]["subsystem"],
                "gpr": targets[rxn_id]["gpr"],
                "definition_of_stoichiometry": targets[rxn_id][
                    "definition_of_stoichiometry"
                ],
                "new_flux_level": target["value"],
                "score": target["score"],
                "knockout": targets[rxn_id]["knockout"],
                "flux_reversal": targets[rxn_id]["flux_reversal"],
                "suddenly_essential": targets[rxn_id]["suddenly_essential"],
            }
            result.append(rxn_data)
        return DataFrame(
            result,
            columns=[
                "reaction_target",
                "reaction_name",
                "subsystem",
                "gpr",
                "definition_of_stoichiometry",
                "new_flux_level",
                "score",
                "knockout",
                "flux_reversal",
                "suddenly_essential",
            ],
        )

    def get_opt_gene_data(self, prediction):
        result = []
        targets = prediction["targets"]
        for gene_id in targets:
            for target in targets[gene_id]:
                gene_data = {
                    "gene_target": gene_id,
                    "gene_name": target["name"],
                    "reaction_id": target["reaction_id"],
                    "reaction_name": target["reaction_name"],
                    "subsystem": target["subsystem"],
                    "gpr": target["gpr"],
                    "definition_of_stoichiometry": target[
                        "definition_of_stoichiometry"
                    ],
                }
                result.append(gene_data)
        return DataFrame(
            result,
            columns=[
                "gene_target",
                "gene_name",
                "reaction_id",
                "reaction_name",
                "subsystem",
                "gpr",
                "definition_of_stoichiometry",
            ],
        )

    def get_cofactor_swap_data(self, prediction):
        result = []
        targets = prediction["targets"]
        manipulations = prediction["manipulations"]
        for target in manipulations:
            rxn_id = target["id"]
            swapped_from = target["from"]
            swapped_to = target["to"]

            rxn_data = {
                "reaction_target": rxn_id,
                "swapped_cofactors": "; ".join(
                    f"{a} -> {b}" for (a, b) in zip(swapped_from, swapped_to)
                ),
                "reaction_name": targets[rxn_id]["name"],
                "subsystem": targets[rxn_id]["subsystem"],
                "gpr": targets[rxn_id]["gpr"],
                "definition_of_stoichiometry": targets[rxn_id][
                    "definition_of_stoichiometry"
                ],
            }
            result.append(rxn_data)
        return DataFrame(
            result,
            columns=[
                "reaction_target",
                "reaction_name",
                "swapped_cofactors",
                "subsystem",
                "gpr",
                "definition_of_stoichiometry",
            ],
        )
