import hmac
import os

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

bp = Blueprint('auth', __name__)


def _credenciais_validas(usuario, senha):
    auth_usuario = os.environ.get('AUTH_USER', '')
    auth_senha = os.environ.get('AUTH_PASSWORD', '')
    return (hmac.compare_digest(usuario or '', auth_usuario)
            and hmac.compare_digest(senha or '', auth_senha))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '')
        senha = request.form.get('senha', '')
        if _credenciais_validas(usuario, senha):
            session.clear()
            session['autenticado'] = True
            session.permanent = True
            destino = request.args.get('next') or url_for('dashboard.dashboard')
            return redirect(destino)
        flash('Usuário ou senha inválidos.', 'danger')

    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))
