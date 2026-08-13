"""Score de priorização — regra de negócio explícita (services/priorizacao.py).

calcular_score() retorna um ScoreResultado: `.score` (int), `.motivos` (lista
estruturada de {'tipo', 'texto', 'classe_css'}) e `.motivo_prioridade`
(string concatenada, derivada da lista — mantida por compatibilidade com a
coluna Cliente.motivo_prioridade, que continua sendo texto simples)."""
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

    resultado = calcular_score(cliente)

    assert resultado.score == PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE
    assert 'Classe A' in resultado.motivo_prioridade
    assert 'risco de queda' in resultado.motivo_prioridade
    assert 'proposta pendente' in resultado.motivo_prioridade

    assert len(resultado.motivos) == 1
    assert resultado.motivos[0]['tipo'] == 'risco_queda'
    assert resultado.motivos[0]['classe_css'] == 'badge-soft-danger'
    assert 'Classe A' in resultado.motivos[0]['texto']


def test_nps_baixo_classe_a_mesmo_sem_risco_de_queda(db):
    cliente = cria_cliente(db, cnpj='10000000000272')
    cria_indicador_retencao(db, cliente, ira_cair=False)
    cria_classe_abc(db, cliente, classe='A')
    cria_nota_nps(db, cliente, nota=4)

    resultado = calcular_score(cliente)

    assert resultado.score == PESO_ALERTA_NPS_BAIXO_CLASSE_A
    assert 'nota NPS 4' in resultado.motivo_prioridade
    assert 'Classe A' in resultado.motivo_prioridade
    assert resultado.motivos[0]['tipo'] == 'nps_baixo'


def test_atraso_na_frequencia_de_compra(db):
    cliente = cria_cliente(db, cnpj='10000000000353')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=90)

    resultado = calcular_score(cliente)

    assert resultado.score == PESO_ATRASO_FREQUENCIA_COMPRA
    assert 'Sem pedido há 90 dias' in resultado.motivo_prioridade
    assert 'Mensal' in resultado.motivo_prioridade
    assert resultado.motivos[0]['tipo'] == 'atraso_frequencia'


def test_sem_nenhum_sinal_score_zero(db):
    cliente = cria_cliente(db, cnpj='10000000000434')

    resultado = calcular_score(cliente)

    assert resultado.score == 0
    assert resultado.motivos == []
    assert resultado.motivo_prioridade == 'Sem sinais de risco identificados'


def test_proposta_critica_isolada(db):
    cliente = cria_cliente(db, cnpj='10000000000515')
    cria_proposta(db, cliente, status_cobranca='Pendente', data_criacao_proposta=dias_atras(30))

    resultado = calcular_score(cliente)

    assert resultado.score == PESO_PROPOSTA_CRITICA
    assert 'parada há' in resultado.motivo_prioridade
    assert resultado.motivos[0]['tipo'] == 'proposta_critica'
    assert resultado.motivos[0]['classe_css'] == 'badge-soft-accent'


def test_multiplos_sinais_somam_pesos_e_concatenam_motivos(db):
    cliente = cria_cliente(db, cnpj='10000000000606')
    cria_indicador_retencao(db, cliente, ira_cair=True, frequencia_compra='Mensal',
                             dias_desde_ultimo_pedido=90)
    cria_classe_abc(db, cliente, classe='B')
    cria_nota_nps(db, cliente, nota=10)  # nota alta: nao deve contar (so conta se classe A)
    cria_proposta(db, cliente, status_cobranca='Pendente', data_criacao_proposta=dias_atras(30))

    resultado = calcular_score(cliente)

    esperado = (PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE + PESO_ATRASO_FREQUENCIA_COMPRA
                + PESO_PROPOSTA_CRITICA)
    assert resultado.score == esperado
    assert 'Classe B' in resultado.motivo_prioridade
    assert 'Sem pedido há 90 dias' in resultado.motivo_prioridade
    assert 'parada há' in resultado.motivo_prioridade
    assert resultado.motivo_prioridade.count(';') == 2  # 3 motivos concatenados

    assert len(resultado.motivos) == 3
    tipos = {m['tipo'] for m in resultado.motivos}
    assert tipos == {'risco_queda', 'atraso_frequencia', 'proposta_critica'}
    # Todo motivo estruturado tem os 3 campos e uma classe CSS válida.
    for motivo in resultado.motivos:
        assert set(motivo.keys()) == {'tipo', 'texto', 'classe_css'}
        assert motivo['classe_css'].startswith('badge-soft-')
