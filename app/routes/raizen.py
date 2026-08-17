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


FILTROS_PENDENCIA_VALIDOS = ('pedidos', 'propostas', 'ambos')


@bp.route('/raizen')
def raizen():
    q = request.args.get('q', '')
    filtro = request.args.get('filtro', '')
    if filtro not in FILTROS_PENDENCIA_VALIDOS:
        filtro = ''  # qualquer valor desconhecido cai em "Todas", nunca quebra a tela

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
        # Sinalizadores de pendência calculados uma vez aqui (não no Jinja) —
        # usados tanto pro filtro "pedidos pendentes / proposta pendente /
        # ambos" quanto pelo template pra decidir cor/ícone do card.
        u.tem_pedido_pendente = any(p.status == 'Pendente' for p in u.pedidos)
        u.tem_proposta_pendente = bool(u.cliente_vinculado) and u.cliente_vinculado.status_cobranca == 'Pendente'

    # Contagens pro rótulo de cada botão de filtro — sobre o resultado da
    # busca (q) mas antes do filtro de pendência ser aplicado, senão o botão
    # que não está ativo sempre mostraria a contagem já filtrada por ele
    # mesmo (inútil pra decidir se vale a pena clicar).
    contagens_filtro = {
        'total': len(unidades),
        'pedidos': sum(1 for u in unidades if u.tem_pedido_pendente),
        'propostas': sum(1 for u in unidades if u.tem_proposta_pendente),
        'ambos': sum(1 for u in unidades if u.tem_pedido_pendente and u.tem_proposta_pendente),
    }

    # O modal "Lançar Pedido" precisa listar TODAS as unidades da busca,
    # mesmo com o filtro de pendência ativo reduzindo os cards visíveis —
    # senão fica impossível lançar pedido pra uma unidade que sumiu da tela
    # por não ter pendência ainda.
    unidades_para_modal = list(unidades)

    if filtro == 'pedidos':
        unidades = [u for u in unidades if u.tem_pedido_pendente]
    elif filtro == 'propostas':
        unidades = [u for u in unidades if u.tem_proposta_pendente]
    elif filtro == 'ambos':
        unidades = [u for u in unidades if u.tem_pedido_pendente and u.tem_proposta_pendente]

    # --- ORDENAÇÃO INTELIGENTE ---
    # 3 = Pedido pendente ou proposta crítica (+15 dias) -> Topo
    # 2 = Tem proposta pendente (sem estar crítica ainda)
    # 1 = Sem pendência ativa, mas tem pedido cobrado
    # 0 = Sem nenhuma pendência
    def get_prioridade(u):
        tem_pedido_cobrado = any(p.status == 'Cobrado' for p in u.pedidos)
        cliente = u.cliente_vinculado
        tem_proposta_critica = bool(cliente) and cliente.dias_parado_maximo > CRITICO_DIAS

        if u.tem_pedido_pendente or tem_proposta_critica:
            return 3
        if u.tem_proposta_pendente:
            return 2
        if tem_pedido_cobrado:
            return 1
        return 0

    unidades = sorted(unidades, key=lambda u: (get_prioridade(u), u.nome), reverse=True)

    return render_template('raizen.html', unidades=unidades, unidades_para_modal=unidades_para_modal,
                           q=q, critico_dias=CRITICO_DIAS, filtro=filtro, contagens_filtro=contagens_filtro)


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
    qtd_propostas_pendentes = sum(1 for p in propostas if p.status_cobranca == 'Pendente')

    filtro = request.args.get('filtro', '')
    if filtro not in FILTROS_PENDENCIA_VALIDOS:
        filtro = ''
    # Mesmo filtro da lista de unidades (/raizen), aplicado aqui só nos dois
    # blocos que são de fato "pendência": Propostas e Pedidos Pendentes
    # ("Precisa de Ação"). Aguardando Retorno (pedido já cobrado) e
    # Histórico (concluído) continuam sempre visíveis — não são pendência,
    # são outra etapa do ciclo de vida do pedido.
    mostrar_pedidos_pendentes = filtro in ('', 'pedidos', 'ambos')
    mostrar_propostas = filtro in ('', 'propostas', 'ambos')

    return render_template('detalhe_unidade.html', unidade=u, pendentes=p1, cobrados=p2, concluidos=p3,
                           cliente=cliente, propostas=propostas, critico_dias=CRITICO_DIAS,
                           qtd_propostas_pendentes=qtd_propostas_pendentes, filtro=filtro,
                           mostrar_pedidos_pendentes=mostrar_pedidos_pendentes, mostrar_propostas=mostrar_propostas)


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
