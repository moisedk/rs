"""add_tags

Revision ID: 5337b0616e8c
Revises: 086c3f46d8af
Create Date: 2024-08-22 08:48:33.081611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5337b0616e8c'
down_revision: Union[str, None] = '086c3f46d8af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('questions', sa.Column('tags', sa.String(length=512), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('questions', 'tags')
    # ### end Alembic commands ###
