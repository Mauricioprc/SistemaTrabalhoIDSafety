"""Monta os dados do Painel de Ação (rota /cobranca): 4 sinais de ação sobre
os clientes — prioridade alta, sem comprar, proposta parada, cliente novo —
e a lista unificada exibida abaixo dos cards/filtros.

Não introduz nenhum dado novo: tudo é derivado de Cliente/Proposta/
IndicadorRetencao já existentes, na hora da requisição.
"""
from datetime import datetime, timedelta

from app.services.priorizacao import CRITICO_DIAS, DIAS_ESPERADOS_POR_FREQUENCIA, calcular_score

SCORE_PRIORIDADE_ALTA = 50   # corte para o sinal "prioridade alta" no painel

# Janela de dias após o cadastro em que um cliente ainda conta como "novo"
# (meio-termo entre os 30-60 dias considerados aceitáveis pelo usuário).
DIAS_CLIENTE_NOVO = 45

# Ordem de prioridade quando um cliente se encaixa em mais de uma categoria
# ao mesmo tempo — decide qual badge/motivo aparece na lista unificada.
# "oportunidade" fica por último de propósito: é o único sinal positivo (chance
# de venda, não problema/risco), então só vira o motivo principal quando o
# cliente não se encaixa em nenhuma categoria de risco.
ORDEM_CATEGORIAS = ('prioridade', 'sem_comprar', 'proposta_parada', 'oportunidade', 'novo')

# Classes ABC consideradas "valiosas o suficiente" pra virar oportunidade de
# reengajamento quando o cliente esfria — mesmo corte usado no score de
# priorização (PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE).
CLASSES_ABC_OPORTUNIDADE = ('A', 'B')

# Faixas de dias parado para o resumo/filtro dentro de "proposta parada".
# Intervalos semiabertos [minimo, maximo) — 15 e 30 e 60 caem na faixa de
# cima, não na de baixo (ex: exatos 30 dias entra em "30-60", não "15-30").
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
    """Agregado pro topo da tela de cobrança: valor total pendente + quebra
    por faixa de dias parado (contagem de clientes e soma de valor_pendente
    em cada uma). Só considera clientes com valor_pendente > 0 — quem está
    em dia não entra em nenhuma faixa."""
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
    if _e_oportunidade(cliente):
        categorias.add('oportunidade')
    if cliente_novo(cliente):
        categorias.add('novo')
    return categorias


def _e_oportunidade(cliente):
    """Cliente Classe A/B, sem risco de queda sinalizado, mas comprando
    menos que o esperado pra frequência dele E sem nenhuma proposta pendente
    em aberto — hoje esse cliente não cai em nenhuma categoria (não é
    "problema" o suficiente pra sem_comprar sozinho chamar atenção, e como
    não tem proposta parada também não aparece em proposta_parada). É uma
    chance de reengajamento ativo, não um risco — por isso a cor é azul
    (badge-soft-info), deliberadamente distinta de vermelho/laranja/verde."""
    retencao = cliente.indicador_retencao
    if not retencao or retencao.ira_cair:
        return False
    classe_atual = cliente.classe_abc_atual
    classe = classe_atual.classe if classe_atual else None
    if classe not in CLASSES_ABC_OPORTUNIDADE:
        return False
    if not _dias_esperado_excedido(cliente):
        return False
    return cliente.qtd_pendentes == 0


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
    """Badge (classes CSS), texto do motivo e (só pra 'prioridade') a lista
    estruturada de motivos — {'tipo', 'texto', 'classe_css'} cada, vinda
    direto de calcular_score(). As outras categorias têm um motivo único que
    já é o suficiente pra explicar, sem precisar de detalhamento."""
    if categoria == 'prioridade':
        score = cliente.score_prioridade or 0
        classe_badge = 'badge-soft-danger' if score >= 100 else 'badge-soft-warning'
        resultado = calcular_score(cliente)
        return classe_badge, str(score), resultado.motivo_prioridade, resultado.motivos

    if categoria == 'sem_comprar':
        info = _dias_esperado_excedido(cliente)
        dias, esperado = info if info else (cliente.indicador_retencao.dias_desde_ultimo_pedido, '—')
        return 'badge-soft-warning', f'{dias}d', f'Sem pedido há {dias} dias (esperado até {esperado} dias)', None

    if categoria == 'proposta_parada':
        dias = cliente.dias_parado_maximo
        return 'badge-soft-accent', cliente.valor_pendente, f'Proposta pendente parada há {dias} dias', None

    if categoria == 'oportunidade':
        info = _dias_esperado_excedido(cliente)
        dias, esperado = info if info else (cliente.indicador_retencao.dias_desde_ultimo_pedido, '—')
        classe = cliente.classe_abc_atual.classe if cliente.classe_abc_atual else '—'
        return ('badge-soft-info', f'{dias}d',
                f'Classe {classe} comprando abaixo do esperado ({dias}d, esperado até {esperado}d) '
                'e sem proposta em aberto — vale contato ativo', None)

    if categoria == 'novo':
        return 'badge-light', 'Novo', 'Cliente novo — nenhuma proposta registrada ainda', None

    return 'badge-light', '', '', None


def montar_painel(clientes, filtro, q):
    """Recebe a lista completa de clientes (já com joinedload/selectinload das
    relações necessárias) e devolve as contagens dos 4 cards e a lista de
    linhas (dict) já filtrada/ordenada para exibição.

    categorias_do_cliente() é calculado uma única vez por cliente (antes
    rodava duas vezes: uma pra montar por_categoria/contagens, outra pra
    montar a lista unificada quando não há filtro)."""
    if q:
        s = q.lower()
        clientes = [c for c in clientes if s in (c.razao_social or '').lower() or s in (c.cnpj or '')]

    categorias_por_cliente = {cliente.id: categorias_do_cliente(cliente) for cliente in clientes}

    contagens = {
        cat: sum(1 for categorias in categorias_por_cliente.values() if cat in categorias)
        for cat in ORDEM_CATEGORIAS
    }

    if filtro in ORDEM_CATEGORIAS:
        linhas = [_linha(c, filtro) for c in clientes if filtro in categorias_por_cliente[c.id]]
    elif filtro in CHAVES_FAIXAS_DIAS_PARADO:
        # Sub-filtro de "proposta parada" por faixa de dias — mesma
        # categoria pra badge/motivo/ordenação, só muda quem entra na lista.
        linhas = [_linha(c, 'proposta_parada') for c in clientes
                  if c.valor_pendente > 0 and _faixa_de_dias_parado(c.dias_parado_maximo) == filtro]
    else:
        linhas = []
        for cliente in clientes:
            categorias = categorias_por_cliente[cliente.id]
            if not categorias:
                continue
            categoria_principal = next(cat for cat in ORDEM_CATEGORIAS if cat in categorias)
            linhas.append(_linha(cliente, categoria_principal))

    linhas.sort(key=_chave_ordenacao)

    return contagens, linhas


def _chave_ordenacao(linha):
    """Ordenação padrão: score_prioridade (maior primeiro) — é urgência
    geral de risco. Mas dentro de "proposta parada" isso não faz sentido: o
    que importa lá é dinheiro parado ponderado pelo tempo parado
    (valor_pendente * dias_parado_maximo), não o risco geral do cliente —
    um cliente pode ter score baixo e ainda assim ser a maior dívida parada
    há mais tempo, e é isso que essa categoria precisa destacar primeiro."""
    cliente = linha['cliente']
    if linha['categoria'] == 'proposta_parada':
        return -(cliente.valor_pendente * cliente.dias_parado_maximo)
    return -(cliente.score_prioridade or 0)


def _linha(cliente, categoria):
    classe_badge, valor_badge, motivo, motivos = badge_e_motivo(cliente, categoria)
    return {
        'cliente': cliente,
        'categoria': categoria,
        'classe_badge': classe_badge,
        'valor_badge': valor_badge,
        'motivo': motivo,
        'motivos': motivos,
    }
