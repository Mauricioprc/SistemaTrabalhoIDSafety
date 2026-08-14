"""Propostas Paradas (services/painel_acao.py) — único propósito: clientes
com proposta parada, ordenados por valor_pendente * dias_parado_maximo."""
from app.services.painel_acao import CHAVES_FAIXAS_DIAS_PARADO, montar_painel, resumo_propostas_paradas
from tests.conftest import cria_cliente, cria_proposta, dias_atras


def test_resumo_propostas_paradas_agrupa_por_faixa_e_soma_valor(db):
    c_0_15 = cria_cliente(db, cnpj='70000000000191')
    cria_proposta(db, c_0_15, status_cobranca='Pendente', data_criacao_proposta=dias_atras(5), valor=100.0)

    c_15_30 = cria_cliente(db, cnpj='70000000000272')
    cria_proposta(db, c_15_30, status_cobranca='Pendente', data_criacao_proposta=dias_atras(20), valor=200.0)

    c_30_60 = cria_cliente(db, cnpj='70000000000353')
    cria_proposta(db, c_30_60, status_cobranca='Pendente', data_criacao_proposta=dias_atras(45), valor=300.0)

    c_60_mais = cria_cliente(db, cnpj='70000000000434')
    cria_proposta(db, c_60_mais, status_cobranca='Pendente', data_criacao_proposta=dias_atras(90), valor=400.0)

    em_dia = cria_cliente(db, cnpj='70000000000515')  # sem proposta pendente — não entra em nenhuma faixa
    db.session.commit()

    clientes = [c_0_15, c_15_30, c_30_60, c_60_mais, em_dia]
    resumo = resumo_propostas_paradas(clientes)

    assert resumo['total_pendente'] == 1000.0
    por_chave = {f['chave']: f for f in resumo['faixas']}
    assert por_chave['parada_0_15'] == {'chave': 'parada_0_15', 'rotulo': '0–15 dias', 'qtd': 1, 'valor': 100.0}
    assert por_chave['parada_15_30'] == {'chave': 'parada_15_30', 'rotulo': '15–30 dias', 'qtd': 1, 'valor': 200.0}
    assert por_chave['parada_30_60'] == {'chave': 'parada_30_60', 'rotulo': '30–60 dias', 'qtd': 1, 'valor': 300.0}
    assert por_chave['parada_60_mais'] == {'chave': 'parada_60_mais', 'rotulo': '60+ dias', 'qtd': 1, 'valor': 400.0}


def test_resumo_propostas_paradas_limites_de_faixa_sao_semiabertos(db):
    """Exatos 15/30/60 dias caem na faixa de cima, não na de baixo."""
    c15 = cria_cliente(db, cnpj='70000000000606')
    cria_proposta(db, c15, status_cobranca='Pendente', data_criacao_proposta=dias_atras(15), valor=50.0)

    c30 = cria_cliente(db, cnpj='70000000000697')
    cria_proposta(db, c30, status_cobranca='Pendente', data_criacao_proposta=dias_atras(30), valor=50.0)

    c60 = cria_cliente(db, cnpj='70000000000778')
    cria_proposta(db, c60, status_cobranca='Pendente', data_criacao_proposta=dias_atras(60), valor=50.0)
    db.session.commit()

    resumo = resumo_propostas_paradas([c15, c30, c60])
    por_chave = {f['chave']: f['qtd'] for f in resumo['faixas']}
    assert por_chave['parada_15_30'] == 1  # o de 15 dias
    assert por_chave['parada_30_60'] == 1  # o de 30 dias
    assert por_chave['parada_60_mais'] == 1  # o de 60 dias
    assert por_chave['parada_0_15'] == 0


def test_montar_painel_so_retorna_clientes_com_proposta_parada(db):
    parado = cria_cliente(db, cnpj='70000000000859')
    cria_proposta(db, parado, status_cobranca='Pendente', data_criacao_proposta=dias_atras(20), valor=10.0)

    recente = cria_cliente(db, cnpj='70000000000930')  # proposta recente, não "parada"
    cria_proposta(db, recente, status_cobranca='Pendente', data_criacao_proposta=dias_atras(2), valor=10.0)

    sem_proposta = cria_cliente(db, cnpj='70000000001001')
    db.session.commit()

    clientes = montar_painel([parado, recente, sem_proposta], filtro='', q='')
    assert [c.id for c in clientes] == [parado.id]


def test_faixa_como_filtro_retorna_so_clientes_daquela_faixa(db):
    perto = cria_cliente(db, cnpj='70000000001010')
    cria_proposta(db, perto, status_cobranca='Pendente', data_criacao_proposta=dias_atras(20), valor=10.0)

    longe = cria_cliente(db, cnpj='70000000001091')
    cria_proposta(db, longe, status_cobranca='Pendente', data_criacao_proposta=dias_atras(90), valor=10.0)
    db.session.commit()

    assert 'parada_60_mais' in CHAVES_FAIXAS_DIAS_PARADO

    clientes = montar_painel([perto, longe], filtro='parada_60_mais', q='')
    assert [c.id for c in clientes] == [longe.id]


def test_busca_por_nome_ou_cnpj_filtra_antes_de_avaliar_parada(db):
    alvo = cria_cliente(db, cnpj='70000000001172', razao_social='EMPRESA ALVO LTDA')
    cria_proposta(db, alvo, status_cobranca='Pendente', data_criacao_proposta=dias_atras(20), valor=10.0)

    outro = cria_cliente(db, cnpj='70000000001253', razao_social='OUTRA EMPRESA LTDA')
    cria_proposta(db, outro, status_cobranca='Pendente', data_criacao_proposta=dias_atras(20), valor=10.0)
    db.session.commit()

    clientes = montar_painel([alvo, outro], filtro='', q='ALVO')
    assert [c.id for c in clientes] == [alvo.id]


def test_ordenacao_usa_valor_vezes_dias_nao_score(db):
    """Cliente com score baixo mas dívida grande/velha deve vir antes de um
    cliente com score alto e dívida pequena/recente — o score não entra
    nessa conta, o único critério é valor_pendente * dias_parado_maximo."""
    divida_grande = cria_cliente(db, cnpj='70000000001334', score_prioridade=10)
    cria_proposta(db, divida_grande, status_cobranca='Pendente', data_criacao_proposta=dias_atras(100), valor=1000.0)

    score_alto_divida_pequena = cria_cliente(db, cnpj='70000000001415', score_prioridade=200)
    cria_proposta(db, score_alto_divida_pequena, status_cobranca='Pendente',
                  data_criacao_proposta=dias_atras(16), valor=10.0)
    db.session.commit()

    clientes = montar_painel([divida_grande, score_alto_divida_pequena], filtro='', q='')

    assert [c.id for c in clientes] == [divida_grande.id, score_alto_divida_pequena.id]


def test_ordenar_dias_ignora_valor_ordena_so_pela_mais_antiga(db):
    antiga_barata = cria_cliente(db, cnpj='70000000001496')
    cria_proposta(db, antiga_barata, status_cobranca='Pendente', data_criacao_proposta=dias_atras(90), valor=10.0)

    recente_cara = cria_cliente(db, cnpj='70000000001577')
    cria_proposta(db, recente_cara, status_cobranca='Pendente', data_criacao_proposta=dias_atras(16), valor=5000.0)
    db.session.commit()

    clientes = montar_painel([antiga_barata, recente_cara], filtro='', q='', ordenar='dias')

    assert [c.id for c in clientes] == [antiga_barata.id, recente_cara.id]


def test_ordenar_valor_ignora_dias_ordena_so_pelo_maior_valor(db):
    antiga_barata = cria_cliente(db, cnpj='70000000001658')
    cria_proposta(db, antiga_barata, status_cobranca='Pendente', data_criacao_proposta=dias_atras(90), valor=10.0)

    recente_cara = cria_cliente(db, cnpj='70000000001739')
    cria_proposta(db, recente_cara, status_cobranca='Pendente', data_criacao_proposta=dias_atras(16), valor=5000.0)
    db.session.commit()

    clientes = montar_painel([antiga_barata, recente_cara], filtro='', q='', ordenar='valor')

    assert [c.id for c in clientes] == [recente_cara.id, antiga_barata.id]


def test_ordenar_valor_invalido_cai_no_padrao(db):
    divida_grande = cria_cliente(db, cnpj='70000000001820', score_prioridade=10)
    cria_proposta(db, divida_grande, status_cobranca='Pendente', data_criacao_proposta=dias_atras(100), valor=1000.0)

    outro = cria_cliente(db, cnpj='70000000001901', score_prioridade=200)
    cria_proposta(db, outro, status_cobranca='Pendente', data_criacao_proposta=dias_atras(16), valor=10.0)
    db.session.commit()

    clientes = montar_painel([divida_grande, outro], filtro='', q='', ordenar='qualquer-coisa-invalida')

    assert [c.id for c in clientes] == [divida_grande.id, outro.id]
