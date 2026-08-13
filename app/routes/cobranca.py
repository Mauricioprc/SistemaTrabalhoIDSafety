from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import Cliente, Proposta
from app.services.importacao.propostas import importar_propostas
from app.services.painel_acao import montar_painel
from app.services.priorizacao import CRITICO_DIAS, recalcular_todos

bp = Blueprint('cobranca', __name__)


@bp.route('/cobranca', methods=['GET', 'POST'])
def cobranca():
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
    filtro = request.args.get('filtro', '')

    todos_clientes = Cliente.query.options(
        selectinload(Cliente.propostas),
        joinedload(Cliente.indicador_retencao),
    ).all()

    contagens, linhas = montar_painel(todos_clientes, filtro, q)

    return render_template('clientes_lista.html', linhas=linhas, contagens=contagens,
                           q=q, filtro=filtro, critico_dias=CRITICO_DIAS)


@bp.route('/proposta/<int:id>/status/<status>', methods=['POST'])
def marcar_status_proposta(id, status):
    p = Proposta.query.get(id)
    if p:
        p.status_cobranca = status
        db.session.commit()
        recalcular_todos()
        flash(f'Proposta #{p.numero_proposta}: {status}.', 'info')
    return redirect(request.referrer or url_for('cobranca.cobranca'))


@bp.route('/cliente/<int:id>/propostas/status/<status>', methods=['POST'])
def marcar_status_propostas_lote(id, status):
    cliente = Cliente.query.get_or_404(id)
    atualizadas = 0
    for p in cliente.propostas:
        if p.status_cobranca == 'Pendente':
            p.status_cobranca = status
            atualizadas += 1
    db.session.commit()
    recalcular_todos()
    flash(f'{atualizadas} proposta(s) marcadas como {status}.', 'info')
    return redirect(request.referrer or url_for('clientes.detalhe_cliente', id=id))
