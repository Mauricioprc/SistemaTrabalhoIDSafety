"""Monta a tela de Propostas Paradas (rota /cobranca) — o único propósito
dessa tela: lembrar cliente que fez cotação e não deu andamento. Sem outras
categorias competindo por atenção (isso mudou para /radar, ver
app/services/radar.py).

Não introduz nenhum dado novo: tudo é derivado de Cliente/Proposta já
existentes, na hora da requisição.
"""
from app.services.priorizacao import CRITICO_DIAS

# Faixas de dias parado para o resumo/filtro da tela. Intervalos semiabertos
# [minimo, maximo) — 15 e 30 e 60 caem na faixa de cima, não na de baixo
# (ex: exatos 30 dias entra em "30-60", não "15-30").
FAIXAS_DIAS_PARADO = (
    ('parada_0_15', '0–15 dias', 0, 15),
    ('parada_15_30', '15–30 dias', 15, 30),
    ('parada_30_60', '30–60 dias', 30, 60),
    ('parada_60_mais', '60+ dias', 60, None),
)
CHAVES_FAIXAS_DIAS_PARADO = frozenset(chave for chave, *_ in FAIXAS_DIAS_PARADO)


def _faixa_de_dias_parado(dias):
    for chave, _rotulo, minimo, maximo in FAIXAS_DIAS_PARADO:
        if dias >= minimo and (maximo is None or dias < maximo):
            return chave
    return None  # não deveria acontecer com as faixas acima (cobrem 0 a infinito)


def resumo_propostas_paradas(clientes):
    """Agregado pro topo da tela: valor total pendente + quebra por faixa de
    dias parado (contagem de clientes e soma de valor_pendente em cada uma).
    Só considera clientes com valor_pendente > 0 — quem está em dia não
    entra em nenhuma faixa."""
    com_pendente = [c for c in clientes if c.valor_pendente > 0]
    total_pendente = sum(c.valor_pendente for c in com_pendente)

    faixas = []
    for chave, rotulo, _minimo, _maximo in FAIXAS_DIAS_PARADO:
        do_grupo = [c for c in com_pendente if _faixa_de_dias_parado(c.dias_parado_maximo) == chave]
        faixas.append({
            'chave': chave,
            'rotulo': rotulo,
            'qtd': len(do_grupo),
            'valor': sum(c.valor_pendente for c in do_grupo),
        })

    return {'total_pendente': total_pendente, 'faixas': faixas}


def montar_painel(clientes, filtro, q):
    """Retorna só os clientes com proposta parada (dias_parado_maximo >
    CRITICO_DIAS), opcionalmente restritos a uma faixa de dias (?filtro=
    parada_0_15/15_30/30_60/60_mais), ordenados por valor_pendente *
    dias_parado_maximo — dinheiro parado ponderado por tempo, não urgência
    geral de risco (esse conceito de "risco geral" saiu daqui, ver
    services/priorizacao.py e o Cliente 360 pra isso)."""
    if q:
        s = q.lower()
        clientes = [c for c in clientes if s in (c.razao_social or '').lower() or s in (c.cnpj or '')]

    parados = [c for c in clientes if c.dias_parado_maximo > CRITICO_DIAS]

    if filtro in CHAVES_FAIXAS_DIAS_PARADO:
        parados = [c for c in parados if _faixa_de_dias_parado(c.dias_parado_maximo) == filtro]

    parados.sort(key=lambda c: -(c.valor_pendente * c.dias_parado_maximo))

    return parados
