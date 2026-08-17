"""Mensagens de reconquista/primeiro contato pro Cliente 360
(templates/detalhe_cliente.html) — a contraparte "o que fazer" de cada
categoria do Radar (app/services/radar.py):

- Cliente comprando abaixo do esperado pra frequência dele -> `contexto_atraso`
  + `mensagens_reconquista` (3 variações, de leve a urgente conforme o
  quanto já passou do prazo e se há risco de queda apontado pelo indicador).
- Cliente novo sem primeira proposta -> `contexto_cliente_novo` +
  `mensagem_primeiro_contato`.

Princípio: toda mensagem cita um dado real do cliente (dias, frequência,
proporção do atraso) em vez de texto genérico — é isso que faz a mensagem
soar como "alguém prestando atenção nele" e não copy-paste. Lógica de
negócio (qual variação sugerir, como formatar os números) fica aqui, não no
Jinja — mesmo princípio já seguido em services/priorizacao.py.
"""
from datetime import datetime, timedelta
from html import escape

from app.services.priorizacao import dias_atraso_frequencia
from app.services.radar import DIAS_CLIENTE_NOVO, cliente_novo


def _para_html(texto):
    """Versão do texto pronta pra ir direto num <div contenteditable> do
    template com `| safe` — escapa HTML (nome de cliente nunca deve virar
    tag) e só DEPOIS troca as quebras de linha por <br>.

    Por que isso não é feito como cadeia de filtros no Jinja
    (`corpo | e | replace('\\n', '<br>') | safe`): o filtro `escape` do
    Jinja devolve um Markup, e o filtro `replace` do Jinja, ao operar sobre
    um Markup, escapa de novo qualquer string nova que você tente inserir
    nele — o '<br>' inserido pelo replace virava literalmente "&lt;br&gt;"
    na tela. Fazendo a troca aqui em Python, com uma string comum (não
    Markup), esse escape duplo não acontece."""
    return escape(texto).replace('\n', '<br>')


# Proporção (dias / esperado) a partir da qual a mensagem sugerida sobe de
# nível. Abaixo de LEVE -> tom de check-in; entre LEVE e URGENTE -> pede
# reunião; a partir de URGENTE (ou com risco de queda apontado pelo
# indicador de retenção) -> tom direto de "não queremos te perder".
LIMIAR_PROPORCAO_REENGAJAMENTO = 1.3
LIMIAR_PROPORCAO_URGENTE = 2.0


def contexto_atraso(cliente, agora=None):
    """Dados pra montar a mensagem de reconquista. None se o cliente não
    estiver com pedido em atraso (mesma regra do Radar, via
    dias_atraso_frequencia — fonte única)."""
    atraso = dias_atraso_frequencia(cliente.indicador_retencao)
    if not atraso:
        return None
    agora = agora or datetime.utcnow()
    dias, esperado = atraso
    proporcao = dias / esperado if esperado else 1
    ira_cair = bool(cliente.indicador_retencao.ira_cair)

    if ira_cair or proporcao >= LIMIAR_PROPORCAO_URGENTE:
        sugestao = 'urgente'
    elif proporcao >= LIMIAR_PROPORCAO_REENGAJAMENTO:
        sugestao = 'reengajamento'
    else:
        sugestao = 'leve'

    return {
        'dias': dias,
        'esperado': esperado,
        'proporcao': proporcao,
        'proporcao_fmt': f'{proporcao:.1f}'.replace('.', ',') + 'x',
        'frequencia': cliente.indicador_retencao.frequencia_compra,
        'ira_cair': ira_cair,
        'data_provavel_ultimo_pedido': agora - timedelta(days=dias),
        'sugestao': sugestao,
    }


def mensagens_reconquista(cliente, contexto):
    """3 variações de mensagem de reconquista, cada uma citando os dados
    reais do cliente (não são só 3 tons do mesmo texto genérico — cada uma
    pede algo diferente: check-in simples, reunião, ou intervenção
    prioritária)."""
    nome = cliente.razao_social
    dias = contexto['dias']
    esperado = contexto['esperado']
    frequencia = contexto['frequencia'] or 'a frequência de compra combinada'
    proporcao_fmt = contexto['proporcao_fmt']

    leve = {
        'titulo': 'Check-in',
        'assunto': f'Faz tempo que não recebemos um pedido — está tudo bem, {nome}?',
        'corpo': (
            'Olá, tudo bem?\n\n'
            f'Aqui a gente acompanha o ritmo de compra de cada cliente, e notei que já se passaram {dias} dias '
            f'desde o último pedido da {nome} — um pouco além do intervalo de {esperado} dias que vocês costumam '
            f'manter ({frequencia}).\n\n'
            'Pode ser só uma pausa natural na operação de vocês, mas quis confirmar: está tudo certo com o '
            'abastecimento? Mudou algo no processo de compra, ou encontraram alguma dificuldade que a gente possa '
            'resolver junto?\n\n'
            'Qualquer coisa, é só me chamar — inclusive se fizer sentido revisar preço ou prazo.\n\n'
            'Abraço,'
        ),
    }
    leve['corpo_html'] = _para_html(leve['corpo'])

    reengajamento = {
        'titulo': 'Reengajamento',
        'assunto': f'Vi que o pedido da {nome} está atrasado — vamos resolver?',
        'corpo': (
            'Olá,\n\n'
            f'Pelo nosso histórico, a {nome} costuma comprar a cada {esperado} dias ({frequencia}) — e já estamos '
            f'em {dias} dias sem um novo pedido, {proporcao_fmt} desse intervalo.\n\n'
            'Queria entender se está faltando algo da nossa parte: prazo, condição de pagamento, disponibilidade '
            'de algum item específico? Me contando o que motivou a pausa, já consigo trazer uma solução ou uma '
            'condição especial pra retomarmos.\n\n'
            'Posso te ligar essa semana pra alinharmos isso?\n\n'
            'Abraço,'
        ),
    }
    reengajamento['corpo_html'] = _para_html(reengajamento['corpo'])

    motivo_risco = (
        ', e nosso indicador de retenção aponta risco real de vocês pararem de comprar com a gente'
        if contexto['ira_cair'] else ''
    )
    urgente = {
        'titulo': 'Risco de perda',
        'assunto': f'Não queremos perder você como cliente, {nome}',
        'corpo': (
            'Olá,\n\n'
            f'Já se passaram {dias} dias sem pedido da {nome} — bem acima do padrão de {esperado} dias que vocês '
            f'costumavam manter{motivo_risco}.\n\n'
            'Antes de perder o contato, prefiro ser direto: o que aconteceu? Perdemos pra concorrência, mudou o '
            'responsável pela compra, ou ficou pendente alguma questão comercial ou de atendimento?\n\n'
            'Consigo priorizar uma conversa esta semana — por telefone, WhatsApp ou pessoalmente — pra entender e '
            'resolver o que for preciso. Vale muito a pena pra nós manter a ' + nome + ' como cliente.\n\n'
            'Fico no aguardo do seu retorno.\n\n'
            'Abraço,'
        ),
    }
    urgente['corpo_html'] = _para_html(urgente['corpo'])

    return {'leve': leve, 'reengajamento': reengajamento, 'urgente': urgente}


def contexto_cliente_novo(cliente, agora=None):
    """Dados pra mensagem de primeiro contato. None se o cliente não for
    'novo' pela regra do Radar (cliente_novo — fonte única)."""
    if not cliente_novo(cliente):
        return None
    agora = agora or datetime.utcnow()
    return {
        'dias_desde_cadastro': (agora - cliente.data_cadastro).days,
        'janela_dias': DIAS_CLIENTE_NOVO,
    }


def mensagem_primeiro_contato(cliente, contexto):
    nome = cliente.razao_social
    dias = contexto['dias_desde_cadastro']
    corpo = (
        'Olá, tudo bem?\n\n'
        f'Vi que a {nome} se cadastrou com a gente {"hoje" if dias == 0 else ("há 1 dia" if dias == 1 else f"há {dias} dias")}, '
        'mas ainda não fechamos o primeiro pedido — não quero deixar essa oportunidade esfriar.\n\n'
        'Posso te ligar pra entender rapidamente o que vocês precisam e já montar uma proposta sob medida? '
        'Costumo conseguir condições melhores quando entendo o cenário de perto.\n\n'
        'Fico à disposição pra marcarmos um horário essa semana.\n\n'
        'Abraço,'
    )
    return {
        'titulo': 'Primeiro contato',
        'assunto': 'Vamos agendar sua primeira compra?',
        'corpo': corpo,
        'corpo_html': _para_html(corpo),
    }
