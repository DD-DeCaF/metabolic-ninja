"""empty message

Revision ID: 23dd297ddbb5
Revises: 50797eac2009
Create Date: 2019-07-06 07:27:23.542983

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '23dd297ddbb5'
down_revision = '50797eac2009'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('design_job', sa.Column('aerobic', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('design_job', 'aerobic')
    # ### end Alembic commands ###
