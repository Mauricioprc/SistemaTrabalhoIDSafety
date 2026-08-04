from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Cliente, Proposta
from app.services.importacao.propostas import importar_propostas
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
    filtro = request.args.get('filtro', 'todos')
    ordenar = request.args.get('ordenar', '')
    ordenar_valor = ordenar == 'valor'
    ordenar_score = ordenar == 'score'

    todos_clientes = Cliente.query.options(joinedload(Cliente.propostas)).all()
    total_pendente = sum(c.valor_pendente for c in todos_clientes)
    total_negociando = sum(c.valor_negociando for c in todos_clientes)
    qtd_pendentes = sum(1 for c in todos_clientes if c.status_cobranca == 'Pendente')
    qtd_negociando = sum(1 for c in todos_clientes if c.status_cobranca == 'Negociando')
    qtd_criticos = sum(1 for c in todos_clientes if c.dias_parado_maximo > CRITICO_DIAS)

    clientes = todos_clientes
    if q:
        s = q.lower()
        clientes = [c for c in clientes if s in (c.razao_social or '').lower() or s in (c.cnpj or '')]

    if filtro == 'pendentes':
        clientes = [c for c in clientes if c.status_cobranca == 'Pendente']
    elif filtro == 'negociando':
        clientes = [c for c in clientes if c.status_cobranca == 'Negociando']
    elif filtro == 'criticos':
        clientes = [c for c in clientes if c.dias_parado_maximo > CRITICO_DIAS]
    elif filtro == 'ok':
        clientes = [c for c in clientes if c.status_cobranca == 'Ok']

    prioridade = {'Pendente': 0, 'Negociando': 1, 'Ok': 2}
    if ordenar_score:
        clientes.sort(key=lambda c: -(c.score_prioridade or 0))
    elif ordenar_valor:
        clientes.sort(key=lambda c: (prioridade.get(c.status_cobranca, 1), -c.valor_pendente))
    else:
        clientes.sort(key=lambda c: (prioridade.get(c.status_cobranca, 1), -c.dias_parado_maximo, -c.valor_pendente))

    return render_template('clientes_lista.html', clientes=clientes, q=q, filtro=filtro,
                           ordenar_valor=ordenar_valor, ordenar_score=ordenar_score,
                           total_pendente=total_pendente, total_negociando=total_negociando,
                           qtd_pendentes=qtd_pendentes, qtd_negociando=qtd_negociando,
                           qtd_criticos=qtd_criticos, critico_dias=CRITICO_DIAS)


@bp.route('/proposta/<int:id>/status/<status>')
def marcar_status_proposta(id, status):
    p = Proposta.query.get(id)
    if p:
        p.status_cobranca = status
        db.session.commit()
        recalcular_todos()
        flash(f'Proposta #{p.numero_proposta}: {status}.', 'info')
    return redirect(request.referrer or url_for('cobranca.cobranca'))


@bp.route('/cliente/<int:id>/propostas/status/<status>')
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
