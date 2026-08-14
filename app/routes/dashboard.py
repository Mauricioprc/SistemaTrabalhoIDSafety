import os

from flask import Blueprint, current_app, flash, redirect, send_file, url_for

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def dashboard():
    """Raiz do sistema — aponta direto pra Propostas Paradas (/cobranca), a
    única tela de "o que fazer agora". Sem dashboard genérico misturando
    métricas de várias áreas."""
    return redirect(url_for('cobranca.cobranca'))


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
