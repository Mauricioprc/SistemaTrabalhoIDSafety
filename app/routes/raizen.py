import os
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Contato, Pedido, Unidade
from app.services.priorizacao import CRITICO_DIAS
from app.utils.formatters import limpar_input

bp = Blueprint('raizen', __name__)


@bp.route('/raizen')
def raizen():
    q = request.args.get('q', '')
    if q:
        s = f"%{q}%"
        l = limpar_input(q)
        unidades = Unidade.query.filter(or_(Unidade.nome.like(s), Unidade.cidade.like(s), Unidade.cnpj.like(l))).all()
    else:
        unidades = Unidade.query.all()

    from app.models import Cliente
    clientes_por_cnpj = {c.cnpj: c for c in Cliente.query.options(joinedload(Cliente.propostas)).all()}
    for u in unidades:
        u.cliente_vinculado = clientes_por_cnpj.get(limpar_input(u.cnpj))

    # --- ORDENAÇÃO INTELIGENTE ---
    # 3 = Pedido pendente ou proposta crítica (+15 dias) -> Topo
    # 2 = Tem proposta pendente (sem estar crítica ainda)
    # 1 = Sem pendência ativa, mas tem pedido cobrado
    # 0 = Sem nenhuma pendência
    def get_prioridade(u):
        tem_pedido_pendente = any(p.status == 'Pendente' for p in u.pedidos)
        tem_pedido_cobrado = any(p.status == 'Cobrado' for p in u.pedidos)
        cliente = u.cliente_vinculado
        tem_proposta_critica = bool(cliente) and cliente.dias_parado_maximo > CRITICO_DIAS
        tem_proposta_pendente = bool(cliente) and cliente.status_cobranca == 'Pendente'

        if tem_pedido_pendente or tem_proposta_critica:
            return 3
        if tem_proposta_pendente:
            return 2
        if tem_pedido_cobrado:
            return 1
        return 0

    unidades = sorted(unidades, key=lambda u: (get_prioridade(u), u.nome), reverse=True)

    return render_template('raizen.html', unidades=unidades, q=q, critico_dias=CRITICO_DIAS)


@bp.route('/marcar_cobrado/<int:id>')
def marcar_cobrado(id):
    p = Pedido.query.get(id)
    if p:
        p.status = 'Cobrado'
        db.session.commit()
        flash('Status: Cobrado.', 'info')
    return redirect(request.referrer or url_for('raizen.raizen'))


@bp.route('/unidade/<int:id>')
def detalhe_unidade(id):
    from app.models import Cliente
    u = Unidade.query.get_or_404(id)
    p1 = Pedido.query.filter_by(unidade_id=id, status='Pendente').order_by(Pedido.data_upload.asc()).all()
    p2 = Pedido.query.filter_by(unidade_id=id, status='Cobrado').order_by(Pedido.data_upload.desc()).all()
    p3 = Pedido.query.filter_by(unidade_id=id, status='Concluído').order_by(Pedido.data_upload.desc()).limit(10).all()

    cnpj_limpo = limpar_input(u.cnpj)
    cliente = Cliente.query.options(joinedload(Cliente.propostas)).filter_by(cnpj=cnpj_limpo).first() if cnpj_limpo else None
    propostas = sorted(cliente.propostas, key=lambda p: p.dias_parado, reverse=True) if cliente else []

    return render_template('detalhe_unidade.html', unidade=u, pendentes=p1, cobrados=p2, concluidos=p3,
                           cliente=cliente, propostas=propostas, critico_dias=CRITICO_DIAS)


@bp.route('/criar_unidade', methods=['POST'])
def criar_unidade():
    nome = request.form.get('nome')
    if nome:
        nova = Unidade(nome=nome, cnpj=limpar_input(request.form.get('cnpj')), cidade=request.form.get('cidade'))
        db.session.add(nova)
        db.session.commit()
        flash('Unidade criada!', 'success')
    return redirect(url_for('raizen.raizen'))


@bp.route('/editar_unidade/<int:id>', methods=['POST'])
def editar_unidade(id):
    u = Unidade.query.get_or_404(id)
    u.nome = request.form.get('nome')
    u.cidade = request.form.get('cidade')
    u.cnpj = limpar_input(request.form.get('cnpj'))
    u.contato = request.form.get('contato')
    u.telefone = request.form.get('telefone')
    u.email = request.form.get('email')
    db.session.commit()
    flash('Atualizado!', 'success')
    return redirect(url_for('raizen.raizen'))


@bp.route('/excluir_unidade/<int:id>', methods=['POST'])
def excluir_unidade(id):
    u = Unidade.query.get_or_404(id)
    db.session.delete(u)
    db.session.commit()
    flash('Excluído!', 'success')
    return redirect(url_for('raizen.raizen'))


@bp.route('/lancar_pedido', methods=['POST'])
def lancar_pedido():
    uid = request.form.get('unidade_id')
    arq = request.files.get('arquivo')
    if uid and arq:
        pasta_pdfs = current_app.config['PASTA_PDFS']
        path = os.path.join(pasta_pdfs, arq.filename.replace(" ", "_"))
        arq.save(path)
        db.session.add(Pedido(arquivo=arq.filename.replace(" ", "_"), unidade_id=uid,
                               observacao=request.form.get('observacao'), data_upload=datetime.now().date()))
        db.session.commit()
        flash('Pedido lançado!', 'success')
    if request.form.get('origem') == 'detalhe':
        return redirect(url_for('raizen.detalhe_unidade', id=uid))
    return redirect(url_for('raizen.raizen'))


@bp.route('/concluir_pedido/<int:id>')
def concluir_pedido(id):
    p = Pedido.query.get(id)
    if p:
        p.status = 'Concluído'
        db.session.commit()
        flash('Concluído!', 'success')
    return redirect(request.referrer or url_for('raizen.raizen'))


@bp.route('/excluir_pedido/<int:id>', methods=['POST'])
def excluir_pedido(id):
    p = Pedido.query.get_or_404(id)
    uid = p.unidade_id
    db.session.delete(p)
    db.session.commit()
    flash('Excluído.', 'success')
    return redirect(url_for('raizen.detalhe_unidade', id=uid))


@bp.route('/editar_pedido_obs/<int:id>', methods=['POST'])
def editar_pedido_obs(id):
    p = Pedido.query.get_or_404(id)
    p.observacao = request.form.get('observacao')
    db.session.commit()
    flash('Atualizado.', 'success')
    return redirect(url_for('raizen.detalhe_unidade', id=p.unidade_id))


@bp.route('/adicionar_contato/<int:unidade_id>', methods=['POST'])
def adicionar_contato(unidade_id):
    nome = request.form.get('nome')
    if nome:
        db.session.add(Contato(nome=nome, cargo=request.form.get('cargo'), telefone=request.form.get('telefone'),
                                email=request.form.get('email'), unidade_id=unidade_id))
        db.session.commit()
        flash('Contato adicionado!', 'success')
    return redirect(url_for('raizen.detalhe_unidade', id=unidade_id))


@bp.route('/editar_contato/<int:id>', methods=['POST'])
def editar_contato(id):
    c = Contato.query.get_or_404(id)
    c.nome = request.form.get('nome')
    c.cargo = request.form.get('cargo')
    c.telefone = request.form.get('telefone')
    c.email = request.form.get('email')
    db.session.commit()
    flash('Contato atualizado!', 'success')
    return redirect(url_for('raizen.detalhe_unidade', id=c.unidade_id))


@bp.route('/excluir_contato/<int:id>', methods=['POST'])
def excluir_contato(id):
    c = Contato.query.get_or_404(id)
    uid = c.unidade_id
    db.session.delete(c)
    db.session.commit()
    flash('Contato removido.', 'success')
    return redirect(url_for('raizen.detalhe_unidade', id=uid))
