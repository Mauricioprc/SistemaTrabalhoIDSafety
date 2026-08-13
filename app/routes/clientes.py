from flask import Blueprint, render_template
from sqlalchemy.orm import joinedload, selectinload

from app.models import Cliente, Unidade
from app.services.priorizacao import CRITICO_DIAS, calcular_score

bp = Blueprint('clientes', __name__)


@bp.route('/cliente/<int:id>')
def detalhe_cliente(id):
    """Cliente 360: dados cadastrais + contatos, propostas, retenção, NPS,
    classe ABC e score/motivo de prioridade em um único lugar."""
    c = Cliente.query.options(
        joinedload(Cliente.propostas),
        joinedload(Cliente.indicador_retencao),
        selectinload(Cliente.classes_abc),
        selectinload(Cliente.notas_nps),
    ).get_or_404(id)

    unidade_vinculada = Unidade.query.filter_by(cnpj=c.cnpj).first() if c.cnpj else None
    contatos = unidade_vinculada.contatos_lista if unidade_vinculada else []
    motivos_prioridade = calcular_score(c).motivos

    return render_template('detalhe_cliente.html', cliente=c, critico_dias=CRITICO_DIAS,
                           unidade_vinculada=unidade_vinculada, contatos=contatos,
                           indicador_retencao=c.indicador_retencao,
                           notas_nps=c.notas_nps, classe_abc_atual=c.classe_abc_atual,
                           motivos_prioridade=motivos_prioridade)
