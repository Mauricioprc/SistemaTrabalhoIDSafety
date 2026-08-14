"""Radar (services/radar.py) — sem_comprar + clientes novos, sem a
categoria 'oportunidade' (removida, não migrada — nunca veio de pedido do
usuário)."""
from app.services.radar import clientes_novos_recentes, clientes_sem_comprar, cliente_novo
from tests.conftest import cria_cliente, cria_indicador_retencao, cria_proposta, dias_atras


# --- sem comprar ---

def test_sem_comprar_acima_do_esperado_pra_frequencia(db):
    cliente = cria_cliente(db, cnpj='80000000000191')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=90)
    db.session.commit()

    resultado = clientes_sem_comprar([cliente])
    assert len(resultado) == 1
    assert resultado[0]['cliente'].id == cliente.id
    assert resultado[0]['dias'] == 90
    assert resultado[0]['esperado'] == 45


def test_nao_aparece_se_dentro_do_esperado(db):
    cliente = cria_cliente(db, cnpj='80000000000272')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=10)
    db.session.commit()

    assert clientes_sem_comprar([cliente]) == []


def test_sem_comprar_ordenado_por_dias_desc(db):
    pouco = cria_cliente(db, cnpj='80000000000353')
    cria_indicador_retencao(db, pouco, frequencia_compra='Mensal', dias_desde_ultimo_pedido=50)

    muito = cria_cliente(db, cnpj='80000000000434')
    cria_indicador_retencao(db, muito, frequencia_compra='Mensal', dias_desde_ultimo_pedido=200)
    db.session.commit()

    resultado = clientes_sem_comprar([pouco, muito])
    assert [item['cliente'].id for item in resultado] == [muito.id, pouco.id]


# --- clientes novos ---

def test_cliente_novo_recente_sem_proposta(db):
    cliente = cria_cliente(db, cnpj='80000000000515', data_cadastro=dias_atras(10))
    db.session.commit()
    assert cliente_novo(cliente) is True


def test_cliente_novo_fora_da_janela_nao_conta(db):
    cliente = cria_cliente(db, cnpj='80000000000606', data_cadastro=dias_atras(90))
    db.session.commit()
    assert cliente_novo(cliente) is False


def test_cliente_sem_data_cadastro_nao_conta(db):
    cliente = cria_cliente(db, cnpj='80000000000697', data_cadastro=None)
    db.session.commit()
    assert cliente_novo(cliente) is False


def test_cliente_novo_com_proposta_nao_conta(db):
    cliente = cria_cliente(db, cnpj='80000000000778', data_cadastro=dias_atras(5))
    cria_proposta(db, cliente, status_cobranca='Pendente', data_criacao_proposta=dias_atras(1))
    db.session.commit()
    assert cliente_novo(cliente) is False


def test_clientes_novos_recentes_ordenado_por_cadastro_mais_recente(db):
    mais_antigo = cria_cliente(db, cnpj='80000000000859', data_cadastro=dias_atras(40))
    mais_novo = cria_cliente(db, cnpj='80000000000930', data_cadastro=dias_atras(2))
    db.session.commit()

    resultado = clientes_novos_recentes([mais_antigo, mais_novo])
    assert [c.id for c in resultado] == [mais_novo.id, mais_antigo.id]
