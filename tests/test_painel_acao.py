"""resumo_propostas_paradas() e a ordenação específica da categoria
'proposta_parada' (valor_pendente * dias_parado_maximo, não score_prioridade)."""
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


def test_faixa_como_filtro_no_painel_retorna_so_clientes_daquela_faixa(db):
    perto = cria_cliente(db, cnpj='70000000000859')
    cria_proposta(db, perto, status_cobranca='Pendente', data_criacao_proposta=dias_atras(5), valor=10.0)

    longe = cria_cliente(db, cnpj='70000000000930')
    cria_proposta(db, longe, status_cobranca='Pendente', data_criacao_proposta=dias_atras(90), valor=10.0)
    db.session.commit()

    assert 'parada_60_mais' in CHAVES_FAIXAS_DIAS_PARADO

    _contagens, linhas = montar_painel([perto, longe], filtro='parada_60_mais', q='')
    ids = {linha['cliente'].id for linha in linhas}
    assert ids == {longe.id}
    assert linhas[0]['categoria'] == 'proposta_parada'


def test_ordenacao_proposta_parada_usa_valor_vezes_dias_nao_score(db):
    """Cliente com score baixo mas dívida grande/velha deve vir antes de um
    cliente com score alto e dívida pequena/recente, dentro dessa categoria."""
    divida_grande = cria_cliente(db, cnpj='70000000001010', score_prioridade=10)
    cria_proposta(db, divida_grande, status_cobranca='Pendente', data_criacao_proposta=dias_atras(100), valor=1000.0)

    score_alto_divida_pequena = cria_cliente(db, cnpj='70000000001091', score_prioridade=200)
    cria_proposta(db, score_alto_divida_pequena, status_cobranca='Pendente',
                  data_criacao_proposta=dias_atras(16), valor=10.0)
    db.session.commit()

    _contagens, linhas = montar_painel(
        [divida_grande, score_alto_divida_pequena], filtro='proposta_parada', q='')

    assert [linha['cliente'].id for linha in linhas] == [divida_grande.id, score_alto_divida_pequena.id]


def test_ordenacao_prioridade_continua_por_score(db):
    """Fora de 'proposta_parada', a ordenação continua sendo por score_prioridade."""
    score_baixo = cria_cliente(db, cnpj='70000000001172', score_prioridade=60)
    score_alto = cria_cliente(db, cnpj='70000000001253', score_prioridade=150)
    db.session.commit()

    _contagens, linhas = montar_painel([score_baixo, score_alto], filtro='prioridade', q='')

    assert [linha['cliente'].id for linha in linhas] == [score_alto.id, score_baixo.id]
