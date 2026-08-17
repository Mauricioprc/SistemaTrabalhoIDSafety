from datetime import datetime

from flask import Blueprint, render_template, request
from sqlalchemy.orm import joinedload, selectinload

from app.models import Cliente
from app.services.radar import FATOR_CRITICO_SEM_COMPRAR, montar_radar, qtd_criticos_sem_comprar

bp = Blueprint('radar', __name__)


@bp.route('/radar')
def radar():
    """Tela secundária: clientes sem comprar recentemente + clientes novos
    sem primeiro contato. Não é a home do sistema — só acessível pelo menu."""
    q = request.args.get('q', '')

    # Filtro de busca vai pro SQL (igual /clientes) em vez de carregar todos
    # os clientes pra filtrar em Python — mesmo raciocínio de N+1/carga
    # desnecessária documentado em services/priorizacao.recalcular_todos().
    consulta = Cliente.query.options(
        selectinload(Cliente.propostas),
        joinedload(Cliente.indicador_retencao),
    )
    if q:
        s = f'%{q}%'
        consulta = consulta.filter(Cliente.razao_social.ilike(s) | Cliente.cnpj.like(s))
    clientes = consulta.all()

    dados = montar_radar(clientes, '')

    return render_template('radar.html', sem_comprar=dados['sem_comprar'], novos=dados['novos'], q=q,
                           agora=datetime.utcnow(),
                           qtd_criticos=qtd_criticos_sem_comprar(dados['sem_comprar']),
                           fator_critico=FATOR_CRITICO_SEM_COMPRAR)
