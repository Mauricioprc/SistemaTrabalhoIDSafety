"""remapeia status Negociando para Pendente

Revision ID: bcecf93b3339
Revises: d0157ea7d483
Create Date: 2026-08-14 13:27:18.912526

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bcecf93b3339'
down_revision = 'd0157ea7d483'
branch_labels = None
depends_on = None


def upgrade():
    # O status "Negociando" foi removido do sistema — essas propostas ainda
    # precisam de ação, então viram "Pendente" (não Ok: não estão resolvidas,
    # só perdemos o estado intermediário). Não apaga nenhum dado, só remapeia.
    proposta = sa.table('proposta', sa.column('status_cobranca', sa.String))
    op.execute(
        proposta.update()
        .where(proposta.c.status_cobranca == 'Negociando')
        .values(status_cobranca='Pendente')
    )


def downgrade():
    # Irreversível de propósito: não há como saber quais dessas propostas
    # "Pendente" eram "Negociando" antes do upgrade.
    pass
