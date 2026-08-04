import os

from flask import Blueprint, current_app, flash, redirect, render_template, send_file, url_for
from sqlalchemy.orm import joinedload

from app.models import Cliente, Pedido, Tarefa, Unidade

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def dashboard():
    total_unidades = Unidade.query.count()
    total_pedidos = Pedido.query.count()

    pedidos_pendentes = Pedido.query.filter_by(status='Pendente').count()
    pedidos_cobrados = Pedido.query.filter_by(status='Cobrado').count()
    pedidos_concluidos = Pedido.query.filter_by(status='Concluído').count()

    ultimos_pedidos = Pedido.query.order_by(Pedido.data_upload.desc()).limit(5).all()

    clientes_ativos = [c for c in Cliente.query.options(joinedload(Cliente.propostas)).all() if c.valor_pendente > 0]
    clientes_ativos.sort(key=lambda c: c.valor_pendente, reverse=True)

    total_divida = sum(c.valor_pendente for c in clientes_ativos)
    qtd_devedores = len(clientes_ativos)
    maior_devedor = clientes_ativos[0] if clientes_ativos else None

    top_devedores = clientes_ativos[:5]
    grafico_nomes = [c.razao_social[:15] + '...' for c in top_devedores]
    grafico_valores = [c.valor_pendente for c in top_devedores]

    tarefas_pendentes = Tarefa.query.filter(Tarefa.status != 'done').count()

    return render_template('dashboard.html',
                           total_unidades=total_unidades,
                           total_pedidos=total_pedidos,
                           pedidos_pendentes=pedidos_pendentes,
                           pedidos_cobrados=pedidos_cobrados,
                           pedidos_concluidos=pedidos_concluidos,
                           ultimos_pedidos=ultimos_pedidos,
                           total_divida=total_divida,
                           qtd_devedores=qtd_devedores,
                           maior_devedor=maior_devedor,
                           tarefas_pendentes=tarefas_pendentes,
                           grafico_nomes=grafico_nomes,
                           grafico_valores=grafico_valores)


@bp.route('/backup')
def backup():
    basedir = current_app.config['BASEDIR']
    db_file = os.path.join(basedir, 'raizen_gestao.db')
    if os.path.exists(db_file):
        from datetime import datetime
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        nome_arquivo = f'backup_sistema_{data_hoje}.db'
        return send_file(db_file, as_attachment=True, download_name=nome_arquivo)
    else:
        flash('Erro: Banco de dados não encontrado.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
