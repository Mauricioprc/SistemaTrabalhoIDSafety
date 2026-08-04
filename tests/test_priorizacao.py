"""Score de priorização — regra de negócio explícita (services/priorizacao.py)."""
from app.services.priorizacao import (
    PESO_ALERTA_NPS_BAIXO_CLASSE_A,
    PESO_ATRASO_FREQUENCIA_COMPRA,
    PESO_PROPOSTA_CRITICA,
    PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE,
    calcular_score,
)
from tests.conftest import cria_classe_abc, cria_cliente, cria_indicador_retencao, cria_nota_nps, cria_proposta, dias_atras


def test_risco_de_queda_classe_ab_com_proposta_pendente(db):
    cliente = cria_cliente(db, cnpj='10000000000191')
    cria_indicador_retencao(db, cliente, ira_cair=True)
    cria_classe_abc(db, cliente, classe='A')
    cria_proposta(db, cliente, status_cobranca='Pendente')

    score, motivo = calcular_score(cliente)

    assert score == PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE
    assert 'Classe A' in motivo
    assert 'risco de queda' in motivo
    assert 'proposta pendente' in motivo


def test_nps_baixo_classe_a_mesmo_sem_risco_de_queda(db):
    cliente = cria_cliente(db, cnpj='10000000000272')
    cria_indicador_retencao(db, cliente, ira_cair=False)
    cria_classe_abc(db, cliente, classe='A')
    cria_nota_nps(db, cliente, nota=4)

    score, motivo = calcular_score(cliente)

    assert score == PESO_ALERTA_NPS_BAIXO_CLASSE_A
    assert 'nota NPS 4' in motivo
    assert 'Classe A' in motivo


def test_atraso_na_frequencia_de_compra(db):
    cliente = cria_cliente(db, cnpj='10000000000353')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=90)

    score, motivo = calcular_score(cliente)

    assert score == PESO_ATRASO_FREQUENCIA_COMPRA
    assert 'Sem pedido há 90 dias' in motivo
    assert 'Mensal' in motivo


def test_sem_nenhum_sinal_score_zero(db):
    cliente = cria_cliente(db, cnpj='10000000000434')

    score, motivo = calcular_score(cliente)

    assert score == 0
    assert motivo == 'Sem sinais de risco identificados'


def test_proposta_critica_isolada(db):
    cliente = cria_cliente(db, cnpj='10000000000515')
    cria_proposta(db, cliente, status_cobranca='Pendente', data_criacao_proposta=dias_atras(30))

    score, motivo = calcular_score(cliente)

    assert score == PESO_PROPOSTA_CRITICA
    assert 'parada há' in motivo


def test_multiplos_sinais_somam_pesos_e_concatenam_motivos(db):
    cliente = cria_cliente(db, cnpj='10000000000606')
    cria_indicador_retencao(db, cliente, ira_cair=True, frequencia_compra='Mensal',
                             dias_desde_ultimo_pedido=90)
    cria_classe_abc(db, cliente, classe='B')
    cria_nota_nps(db, cliente, nota=10)  # nota alta: nao deve contar (so conta se classe A)
    cria_proposta(db, cliente, status_cobranca='Pendente', data_criacao_proposta=dias_atras(30))

    score, motivo = calcular_score(cliente)

    esperado = (PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE + PESO_ATRASO_FREQUENCIA_COMPRA
                + PESO_PROPOSTA_CRITICA)
    assert score == esperado
    assert 'Classe B' in motivo
    assert 'Sem pedido há 90 dias' in motivo
    assert 'parada há' in motivo
    assert motivo.count(';') == 2  # 3 motivos concatenados
