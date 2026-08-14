from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Cliente, Proposta
from app.models.proposta import STATUS_COBRANCA_VALIDOS
from app.services.importacao.propostas import importar_propostas
from app.services.painel_acao import montar_painel, resumo_propostas_paradas
from app.services.priorizacao import CRITICO_DIAS, recalcular_todos

bp = Blueprint('cobranca', __name__)


@bp.route('/cobranca', methods=['GET', 'POST'])
def cobranca():
    """Propostas Paradas — página inicial do sistema. Um único propósito:
    lembrar cliente que fez cotação e não deu andamento."""
    if request.method == 'POST':
        arquivo = request.files.get('planilha')
        if arquivo:
            try:
                resultado = importar_propostas(arquivo)
                recalcular_todos()
                flash(f"Processado! {resultado['clientes_novos']} clientes novos, "
                      f"{resultado['propostas_novas']} propostas novas, "
                      f"{resultado['propostas_atualizadas']} atualizadas, "
                      f"{resultado['propostas_removidas']} removidas.", 'success')
            except Exception as e:
                flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('cobranca.cobranca'))

    q = request.args.get('q', '')
    filtro = request.args.get('filtro', '')  # faixa de dias parado (parada_0_15/15_30/30_60/60_mais)

    todos_clientes = Cliente.query.options(selectinload(Cliente.propostas)).all()

    clientes_parados = montar_painel(todos_clientes, filtro, q)
    resumo_paradas = resumo_propostas_paradas(todos_clientes)

    return render_template('painel_acao.html', clientes=clientes_parados,
                           resumo_paradas=resumo_paradas,
                           q=q, filtro=filtro, critico_dias=CRITICO_DIAS)


@bp.route('/proposta/<int:id>/status/<status>', methods=['POST'])
def marcar_status_proposta(id, status):
    if status not in STATUS_COBRANCA_VALIDOS:
        flash(f'Status inválido: {status}.', 'danger')
        return redirect(request.referrer or url_for('cobranca.cobranca'))

    p = Proposta.query.get(id)
    if p:
        p.status_cobranca = status
        p.data_ultima_mudanca_status = datetime.utcnow()
        db.session.commit()
        recalcular_todos()
        flash(f'Proposta #{p.numero_proposta}: {status}.', 'info')
    return redirect(request.referrer or url_for('cobranca.cobranca'))


@bp.route('/cliente/<int:id>/propostas/status/<status>', methods=['POST'])
def marcar_status_propostas_lote(id, status):
    if status not in STATUS_COBRANCA_VALIDOS:
        flash(f'Status inválido: {status}.', 'danger')
        return redirect(request.referrer or url_for('clientes.detalhe_cliente', id=id))

    cliente = Cliente.query.get_or_404(id)
    atualizadas = 0
    agora = datetime.utcnow()
    for p in cliente.propostas:
        if p.status_cobranca == 'Pendente':
            p.status_cobranca = status
            p.data_ultima_mudanca_status = agora
            atualizadas += 1
    db.session.commit()
    recalcular_todos()
    flash(f'{atualizadas} proposta(s) marcadas como {status}.', 'info')
    return redirect(request.referrer or url_for('clientes.detalhe_cliente', id=id))
