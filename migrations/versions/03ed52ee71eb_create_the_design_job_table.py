"""Create the design job table

Revision ID: 03ed52ee71eb
Revises:
Create Date: 2018-11-06 19:25:10.040962

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '03ed52ee71eb'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('design_job',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('model_id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.String(length=36), nullable=False),
    sa.Column('is_complete', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=8), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('task_id')
    )
    op.create_index(op.f('ix_design_job_project_id'), 'design_job', ['project_id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_design_job_project_id'), table_name='design_job')
    op.drop_table('design_job')
    # ### end Alembic commands ###
