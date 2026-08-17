from urllib.parse import urlparse

from flask import Blueprint, render_template, request, url_for
from sqlalchemy.orm import joinedload, selectinload

from app.models import Cliente, Unidade
from app.services.priorizacao import CRITICO_DIAS, calcular_score
from app.services.radar import cliente_novo, cliente_sem_comprar
from app.services.reconquista import (
    contexto_atraso, contexto_cliente_novo, mensagem_primeiro_contato, mensagens_reconquista,
)

bp = Blueprint('clientes', __name__)

# Path -> (endpoint, rótulo do botão "Voltar") no Cliente 360. Cliente 360 é
# aberto a partir de vários lugares (Radar, Clientes, Raízen, Painel de
# Ação) — o botão de voltar tinha um link fixo pro Painel de Ação, então
# vindo do Radar ele te jogava pro lugar errado. Cobrimos pelo path porque
# request.referrer é uma URL completa (com querystring) e sempre bate no
# prefixo da rota de origem, mesmo com ?q=... etc.
DESTINOS_VOLTAR = [
    ('/radar', 'radar.radar', 'Voltar para o Radar'),
    ('/clientes', 'clientes.lista', 'Voltar para Clientes'),
    ('/cliente', 'clientes.lista', 'Voltar para Clientes'),  # veio de outro Cliente 360 (raro, mas possível)
    ('/raizen', 'raizen.raizen', 'Voltar para Raízen'),
    ('/cobranca', 'cobranca.cobranca', 'Voltar para o Painel de ação'),
]


def _resolver_voltar():
    """Decide o destino do botão 'Voltar' do Cliente 360 a partir de quem
    encaminhou pra cá (request.referrer). Sem referrer confiável (acesso
    direto pela URL, por exemplo), cai no Painel de Ação — home do sistema,
    mesmo fallback de sempre."""
    referrer = request.referrer
    if referrer:
        path = urlparse(referrer).path
        for prefixo, endpoint, rotulo in DESTINOS_VOLTAR:
            if path.startswith(prefixo):
                return url_for(endpoint), rotulo
    return url_for('cobranca.cobranca'), 'Voltar para o Painel de ação'


@bp.route('/clientes')
def lista():
    """Tabela geral com TODOS os clientes (611+) — densa, sem o filtro do
    Painel de Ação (/cobranca). Esse é o cadastro completo; o painel é a
    visão de "o que fazer agora" sobre um subconjunto dele."""
    q = request.args.get('q', '')

    consulta = Cliente.query.options(
        selectinload(Cliente.propostas),
        selectinload(Cliente.classes_abc),
        selectinload(Cliente.notas_nps),
        joinedload(Cliente.indicador_retencao),
    )
    if q:
        s = f'%{q}%'
        consulta = consulta.filter(Cliente.razao_social.ilike(s) | Cliente.cnpj.like(s))

    clientes = consulta.order_by(Cliente.score_prioridade.desc().nullslast(),
                                 Cliente.razao_social.asc()).all()

    # IDs presentes no Radar (sem comprar no esperado ou cliente novo sem
    # contato) — usado só pra mostrar um badge de aviso aqui, sem duplicar a
    # regra de negócio no template (ver app/services/radar.py).
    ids_no_radar = {c.id for c in clientes if cliente_sem_comprar(c) or cliente_novo(c)}

    # Resumo do topo da tela — cálculo aqui, não no Jinja, pelo mesmo
    # princípio já seguido no resto do projeto (lógica fora do template).
    resumo = {
        'total': len(clientes),
        'pendentes': sum(1 for c in clientes if c.status_cobranca == 'Pendente'),
        'valor_pendente': sum(c.valor_pendente for c in clientes),
        'no_radar': len(ids_no_radar),
    }

    return render_template('clientes_lista.html', clientes=clientes, q=q, critico_dias=CRITICO_DIAS,
                           ids_no_radar=ids_no_radar, resumo=resumo)


@bp.route('/cliente/<int:id>/propostas')
def propostas_cliente(id):
    """Tela enxuta de Propostas Paradas do cliente — só propostas
    pendentes, valores totais, contato de cobrança e as mensagens prontas.
    É pra onde o Painel de Ação (/cobranca) leva ao clicar em "Ver
    proposta"; o Cliente 360 completo continua em /cliente/<id>."""
    c = Cliente.query.options(joinedload(Cliente.propostas)).get_or_404(id)
    return render_template('propostas_cliente.html', cliente=c, critico_dias=CRITICO_DIAS)


@bp.route('/cliente/<int:id>')
def detalhe_cliente(id):
    """Cliente 360: dados cadastrais + contatos, propostas, retenção, NPS,
    classe ABC e score/motivo de prioridade em um único lugar."""
    c = Cliente.query.options(
        joinedload(Cliente.propostas),
        joinedload(Cliente.indicador_retencao),
        selectinload(Cliente.classes_abc),
        selectinload(Cliente.notas_nps),
    ).get_or_404(id)

    unidade_vinculada = Unidade.query.filter_by(cnpj=c.cnpj).first() if c.cnpj else None
    contatos = unidade_vinculada.contatos_lista if unidade_vinculada else []
    motivos_prioridade = calcular_score(c).motivos
    no_radar = cliente_sem_comprar(c) or cliente_novo(c)

    # Contexto + mensagens de reconquista (cliente comprando abaixo do
    # esperado) ou de primeiro contato (cliente novo sem proposta) — no
    # máximo um dos dois se aplica, nunca os dois (ver services/radar.py).
    ctx_atraso = contexto_atraso(c)
    msgs_reconquista = mensagens_reconquista(c, ctx_atraso) if ctx_atraso else None

    ctx_novo = contexto_cliente_novo(c)
    msg_primeiro_contato = mensagem_primeiro_contato(c, ctx_novo) if ctx_novo else None

    voltar_url, voltar_rotulo = _resolver_voltar()

    return render_template('detalhe_cliente.html', cliente=c, critico_dias=CRITICO_DIAS,
                           unidade_vinculada=unidade_vinculada, contatos=contatos,
                           indicador_retencao=c.indicador_retencao,
                           notas_nps=c.notas_nps, classe_abc_atual=c.classe_abc_atual,
                           motivos_prioridade=motivos_prioridade, no_radar=no_radar,
                           ctx_atraso=ctx_atraso, msgs_reconquista=msgs_reconquista,
                           ctx_novo=ctx_novo, msg_primeiro_contato=msg_primeiro_contato,
                           voltar_url=voltar_url, voltar_rotulo=voltar_rotulo)
