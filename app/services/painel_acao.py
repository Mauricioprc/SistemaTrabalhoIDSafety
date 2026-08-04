"""Monta os dados do Painel de Ação (rota /cobranca): 4 sinais de ação sobre
os clientes — prioridade alta, sem comprar, proposta parada, cliente novo —
e a lista unificada exibida abaixo dos cards/filtros.

Não introduz nenhum dado novo: tudo é derivado de Cliente/Proposta/
IndicadorRetencao já existentes, na hora da requisição.
"""
from datetime import datetime, timedelta

from app.services.priorizacao import CRITICO_DIAS, DIAS_ESPERADOS_POR_FREQUENCIA

SCORE_PRIORIDADE_ALTA = 50   # corte para o sinal "prioridade alta" no painel

# Janela de dias após o cadastro em que um cliente ainda conta como "novo"
# (meio-termo entre os 30-60 dias considerados aceitáveis pelo usuário).
DIAS_CLIENTE_NOVO = 45

# Ordem de prioridade quando um cliente se encaixa em mais de uma categoria
# ao mesmo tempo — decide qual badge/motivo aparece na lista unificada.
ORDEM_CATEGORIAS = ('prioridade', 'sem_comprar', 'proposta_parada', 'novo')


def _dias_esperado_excedido(cliente):
    retencao = cliente.indicador_retencao
    if not retencao or retencao.frequencia_compra not in DIAS_ESPERADOS_POR_FREQUENCIA:
        return None
    esperado = DIAS_ESPERADOS_POR_FREQUENCIA[retencao.frequencia_compra]
    dias = retencao.dias_desde_ultimo_pedido or 0
    if dias > esperado:
        return dias, esperado
    return None


def categorias_do_cliente(cliente):
    """Retorna o conjunto de categorias de ação em que o cliente se encaixa."""
    categorias = set()
    if (cliente.score_prioridade or 0) >= SCORE_PRIORIDADE_ALTA:
        categorias.add('prioridade')
    if _dias_esperado_excedido(cliente):
        categorias.add('sem_comprar')
    if cliente.dias_parado_maximo > CRITICO_DIAS:
        categorias.add('proposta_parada')
    if cliente_novo(cliente):
        categorias.add('novo')
    return categorias


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


def badge_e_motivo(cliente, categoria):
    """Badge (classes CSS) e texto do motivo para uma categoria específica."""
    if categoria == 'prioridade':
        score = cliente.score_prioridade or 0
        classe_badge = 'badge-soft-danger' if score >= 100 else 'badge-soft-warning'
        return classe_badge, str(score), (cliente.motivo_prioridade or 'Sinais de risco identificados')

    if categoria == 'sem_comprar':
        info = _dias_esperado_excedido(cliente)
        dias, esperado = info if info else (cliente.indicador_retencao.dias_desde_ultimo_pedido, '—')
        return 'badge-soft-warning', f'{dias}d', f'Sem pedido há {dias} dias (esperado até {esperado} dias)'

    if categoria == 'proposta_parada':
        dias = cliente.dias_parado_maximo
        return 'badge-soft-accent', cliente.valor_pendente, f'Proposta pendente parada há {dias} dias'

    if categoria == 'novo':
        return 'badge-light', 'Novo', 'Cliente novo — nenhuma proposta registrada ainda'

    return 'badge-light', '', ''


def montar_painel(clientes, filtro, q):
    """Recebe a lista completa de clientes (já com joinedload das relações
    necessárias) e devolve as contagens dos 4 cards e a lista de linhas
    (dict) já filtrada/ordenada para exibição."""
    if q:
        s = q.lower()
        clientes = [c for c in clientes if s in (c.razao_social or '').lower() or s in (c.cnpj or '')]

    por_categoria = {cat: [] for cat in ORDEM_CATEGORIAS}
    for cliente in clientes:
        for categoria in categorias_do_cliente(cliente):
            por_categoria[categoria].append(cliente)

    contagens = {cat: len(por_categoria[cat]) for cat in ORDEM_CATEGORIAS}

    if filtro in ORDEM_CATEGORIAS:
        clientes_do_filtro = por_categoria[filtro]
        linhas = [_linha(c, filtro) for c in clientes_do_filtro]
    else:
        vistos = set()
        linhas = []
        for cliente in clientes:
            categorias = categorias_do_cliente(cliente)
            if not categorias or cliente.id in vistos:
                continue
            categoria_principal = next(cat for cat in ORDEM_CATEGORIAS if cat in categorias)
            linhas.append(_linha(cliente, categoria_principal))
            vistos.add(cliente.id)

    linhas.sort(key=lambda linha: -(linha['cliente'].score_prioridade or 0))

    return contagens, linhas


def _linha(cliente, categoria):
    classe_badge, valor_badge, motivo = badge_e_motivo(cliente, categoria)
    return {
        'cliente': cliente,
        'categoria': categoria,
        'classe_badge': classe_badge,
        'valor_badge': valor_badge,
        'motivo': motivo,
    }
