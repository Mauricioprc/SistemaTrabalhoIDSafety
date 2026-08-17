"""Radar (services/radar.py) — sem_comprar + clientes novos, sem a
categoria 'oportunidade' (removida, não migrada — nunca veio de pedido do
usuário)."""
from app.services.radar import (
    clientes_novos_recentes, clientes_sem_comprar, cliente_novo, cliente_sem_comprar,
)
from app.services.priorizacao import dias_atraso_frequencia, calcular_score
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


# --- regra de atraso unificada com o score de priorização ---
# Antes o Radar tinha sua própria cópia de "dias sem pedido acima do
# esperado" (services/radar._dias_esperado_excedido, removida). Agora as
# duas rotas usam app.services.priorizacao.dias_atraso_frequencia — estes
# testes travam que ela concorda com clientes_sem_comprar/cliente_sem_comprar
# e com o motivo 'atraso_frequencia' do score.

def test_cliente_sem_comprar_usa_a_mesma_regra_do_score_de_priorizacao(db):
    cliente = cria_cliente(db, cnpj='80000000001011')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=90)
    db.session.commit()

    assert cliente_sem_comprar(cliente) is True
    assert dias_atraso_frequencia(cliente.indicador_retencao) == (90, 45)
    motivos_tipos = {m['tipo'] for m in calcular_score(cliente).motivos}
    assert 'atraso_frequencia' in motivos_tipos


def test_cliente_sem_comprar_false_quando_dentro_do_esperado(db):
    cliente = cria_cliente(db, cnpj='80000000001092')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=10)
    db.session.commit()

    assert cliente_sem_comprar(cliente) is False
    motivos_tipos = {m['tipo'] for m in calcular_score(cliente).motivos}
    assert 'atraso_frequencia' not in motivos_tipos


def test_cliente_sem_comprar_false_sem_indicador_retencao(db):
    cliente = cria_cliente(db, cnpj='80000000001173')
    db.session.commit()

    assert cliente_sem_comprar(cliente) is False


# --- rota /radar: busca via SQL, não em memória ---

def test_rota_radar_busca_filtra_por_razao_social(client, db):
    alvo = cria_cliente(db, cnpj='80000000001254', razao_social='Empresa Alvo LTDA')
    cria_indicador_retencao(db, alvo, frequencia_compra='Mensal', dias_desde_ultimo_pedido=90)
    outro = cria_cliente(db, cnpj='80000000001335', razao_social='Outra Empresa LTDA')
    cria_indicador_retencao(db, outro, frequencia_compra='Mensal', dias_desde_ultimo_pedido=90)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get('/radar?q=Alvo')
    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert 'Empresa Alvo LTDA' in corpo
    assert 'Outra Empresa LTDA' not in corpo


def test_rota_radar_busca_por_cnpj(client, db):
    alvo = cria_cliente(db, cnpj='80000000001416', razao_social='Cliente Buscado LTDA', data_cadastro=dias_atras(1))
    outro = cria_cliente(db, cnpj='80000000001497', razao_social='Cliente Nao Buscado LTDA', data_cadastro=dias_atras(1))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get('/radar?q=80000000001416')
    corpo = resposta.get_data(as_text=True)
    assert 'Cliente Buscado LTDA' in corpo
    assert 'Cliente Nao Buscado LTDA' not in corpo


# --- rota /clientes: cross-link com o Radar ---

def test_rota_clientes_mostra_badge_radar_para_cliente_sem_comprar(client, db):
    cliente = cria_cliente(db, cnpj='80000000001578', razao_social='Cliente No Radar LTDA')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=90)
    fora_do_radar = cria_cliente(db, cnpj='80000000001659', razao_social='Cliente Fora Do Radar LTDA')
    cria_indicador_retencao(db, fora_do_radar, frequencia_compra='Mensal', dias_desde_ultimo_pedido=10)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get('/clientes')
    corpo = resposta.get_data(as_text=True)
    # 'Aparece no Radar' é o title do badge por linha — específico o
    # suficiente pra não colidir com o link "Radar" do card de resumo do
    # topo da página (que sempre aparece, tenha ou não cliente no radar).
    assert corpo.count('Aparece no Radar') == 1
