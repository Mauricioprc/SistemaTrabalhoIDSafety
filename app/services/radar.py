"""Radar (rota /radar) — sinais secundários sobre clientes: comprando abaixo
do esperado pra frequência deles, e clientes novos que ainda não tiveram
primeiro contato. Tela secundária, acessível só por link no menu — a home
do sistema é Propostas Paradas (/cobranca, ver services/painel_acao.py).

Não tem categoria "oportunidade" aqui de propósito: isso nunca veio de um
pedido do usuário, foi adicionado sem necessidade e foi removido, não
migrado.
"""
from datetime import datetime, timedelta

from app.services.priorizacao import dias_atraso_frequencia

# Janela de dias após o cadastro em que um cliente ainda conta como "novo"
# (meio-termo entre os 30-60 dias considerados aceitáveis pelo usuário).
DIAS_CLIENTE_NOVO = 45


def cliente_novo(cliente):
    """Cliente novo = cadastro recente (dentro de DIAS_CLIENTE_NOVO) e ainda
    sem nenhuma Proposta. Clientes com data_cadastro=NULL (toda a base
    anterior a esse campo existir) nunca entram aqui — não há como saber se
    são recentes, então ficam de fora em vez de aparecerem errado."""
    if cliente.data_cadastro is None:
        return False
    if len(cliente.propostas) > 0:
        return False
    limite = datetime.utcnow() - timedelta(days=DIAS_CLIENTE_NOVO)
    return cliente.data_cadastro >= limite


def cliente_sem_comprar(cliente):
    """True se o cliente estiver com dias sem pedido acima do esperado pra
    frequência de compra dele. Mesma regra usada no score de priorização
    (services/priorizacao.dias_atraso_frequencia) — fonte única, evita as
    duas telas divergirem silenciosamente."""
    return dias_atraso_frequencia(cliente.indicador_retencao) is not None


def clientes_sem_comprar(clientes):
    """Clientes com indicador de retenção mostrando dias sem pedido acima do
    esperado pra frequência de compra deles. Ordenado por dias (mais tempo
    sem comprar primeiro)."""
    resultado = []
    for cliente in clientes:
        info = dias_atraso_frequencia(cliente.indicador_retencao)
        if info:
            dias, esperado = info
            resultado.append({'cliente': cliente, 'dias': dias, 'esperado': esperado})
    resultado.sort(key=lambda item: -item['dias'])
    return resultado


# Fator sobre o "esperado" a partir do qual um item de "sem comprar" é
# tratado como caso crítico na UI (borda/badge vermelha em vez de amarela).
FATOR_CRITICO_SEM_COMPRAR = 2


def qtd_criticos_sem_comprar(sem_comprar):
    """Conta quantos itens de clientes_sem_comprar() já passaram de
    FATOR_CRITICO_SEM_COMPRAR vezes o prazo esperado — usado só pro resumo
    da tela do Radar, cálculo fora do template por consistência com o resto
    do projeto (ver CLASSE_CSS_POR_TIPO_MOTIVO em services/priorizacao.py)."""
    return sum(1 for item in sem_comprar if item['dias'] >= item['esperado'] * FATOR_CRITICO_SEM_COMPRAR)


def clientes_novos_recentes(clientes):
    """Clientes novos (ver cliente_novo), ordenados por cadastro mais recente primeiro."""
    novos = [c for c in clientes if cliente_novo(c)]
    novos.sort(key=lambda c: c.data_cadastro, reverse=True)
    return novos


def montar_radar(clientes, q):
    if q:
        s = q.lower()
        clientes = [c for c in clientes if s in (c.razao_social or '').lower() or s in (c.cnpj or '')]

    return {
        'sem_comprar': clientes_sem_comprar(clientes),
        'novos': clientes_novos_recentes(clientes),
    }
