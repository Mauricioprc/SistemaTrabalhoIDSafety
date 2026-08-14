from flask import Blueprint, render_template, request
from sqlalchemy.orm import joinedload, selectinload

from app.models import Cliente
from app.services.radar import montar_radar

bp = Blueprint('radar', __name__)


@bp.route('/radar')
def radar():
    """Tela secundária: clientes sem comprar recentemente + clientes novos
    sem primeiro contato. Não é a home do sistema — só acessível pelo menu."""
    q = request.args.get('q', '')

    clientes = Cliente.query.options(
        selectinload(Cliente.propostas),
        joinedload(Cliente.indicador_retencao),
    ).all()

    dados = montar_radar(clientes, q)

    return render_template('radar.html', sem_comprar=dados['sem_comprar'], novos=dados['novos'], q=q)
