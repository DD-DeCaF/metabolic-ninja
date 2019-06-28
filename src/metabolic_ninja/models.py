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

from flask_sqlalchemy import SQLAlchemy
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
