"""Filtro de pendência (Pedidos pendentes / Proposta pendente / Ambos) nas
telas do Raízen — lista de unidades (/raizen) e detalhe (/unidade/<id>)."""
from datetime import date

from app.models import Pedido, Unidade
from tests.conftest import cria_cliente, cria_proposta


def cria_unidade(db, nome, cnpj, cidade='Cidade Teste'):
    u = Unidade(nome=nome, cnpj=cnpj, cidade=cidade)
    db.session.add(u)
    db.session.flush()
    return u


def cria_pedido(db, unidade, status='Pendente'):
    p = Pedido(arquivo=f'pedido-{unidade.id}-{status}.pdf', unidade_id=unidade.id, status=status,
               data_upload=date.today())
    db.session.add(p)
    db.session.flush()
    return p


def _login(client):
    with client.session_transaction() as sess:
        sess['autenticado'] = True


# --- /raizen (lista) ---

def test_raizen_sem_filtro_mostra_todas_unidades(client, db):
    cria_unidade(db, 'Unidade A', '10000000000191')
    cria_unidade(db, 'Unidade B', '10000000000272')
    db.session.commit()
    _login(client)

    resposta = client.get('/raizen')
    corpo = resposta.get_data(as_text=True)
    assert 'Unidade A' in corpo
    assert 'Unidade B' in corpo


def test_raizen_filtro_pedidos_mostra_so_unidade_com_pedido_pendente(client, db):
    com_pedido = cria_unidade(db, 'Unidade Com Pedido', '10000000000353')
    cria_pedido(db, com_pedido, status='Pendente')
    sem_pedido = cria_unidade(db, 'Unidade Sem Pedido', '10000000000434')
    db.session.commit()
    _login(client)

    resposta = client.get('/raizen?filtro=pedidos')
    corpo = resposta.get_data(as_text=True)
    assert f'/unidade/{com_pedido.id}"' in corpo
    # A unidade sem pedido pendente não deve aparecer como CARD — ela ainda
    # aparece como <option> no modal "Lançar Pedido" (comportamento
    # intencional, ver test_raizen_modal_lancar_pedido_...), então checamos
    # especificamente o link do card, não o nome cru.
    assert f'/unidade/{sem_pedido.id}"' not in corpo


def test_raizen_filtro_propostas_mostra_so_unidade_com_proposta_pendente(client, db):
    cnpj_com = '10000000000515'
    com_proposta = cria_unidade(db, 'Unidade Com Proposta', cnpj_com)
    cliente = cria_cliente(db, cnpj=cnpj_com, razao_social='Cliente Vinculado LTDA')
    cria_proposta(db, cliente, status_cobranca='Pendente')
    sem_proposta = cria_unidade(db, 'Unidade Sem Proposta', '10000000000606')
    db.session.commit()
    _login(client)

    resposta = client.get('/raizen?filtro=propostas')
    corpo = resposta.get_data(as_text=True)
    assert f'/unidade/{com_proposta.id}"' in corpo
    assert f'/unidade/{sem_proposta.id}"' not in corpo


def test_raizen_filtro_ambos_exige_pedido_e_proposta_pendentes(client, db):
    cnpj_ambos = '10000000000687'
    ambos = cria_unidade(db, 'Unidade Ambos', cnpj_ambos)
    cria_pedido(db, ambos, status='Pendente')
    cliente = cria_cliente(db, cnpj=cnpj_ambos, razao_social='Cliente Ambos LTDA')
    cria_proposta(db, cliente, status_cobranca='Pendente')

    so_pedido = cria_unidade(db, 'Unidade So Pedido', '10000000000768')
    cria_pedido(db, so_pedido, status='Pendente')

    cnpj_so_proposta = '10000000000849'
    so_proposta = cria_unidade(db, 'Unidade So Proposta', cnpj_so_proposta)
    cliente2 = cria_cliente(db, cnpj=cnpj_so_proposta, razao_social='Cliente So Proposta LTDA')
    cria_proposta(db, cliente2, status_cobranca='Pendente')

    db.session.commit()
    _login(client)

    resposta = client.get('/raizen?filtro=ambos')
    corpo = resposta.get_data(as_text=True)
    assert f'/unidade/{ambos.id}"' in corpo
    assert f'/unidade/{so_pedido.id}"' not in corpo
    assert f'/unidade/{so_proposta.id}"' not in corpo


def test_raizen_filtro_invalido_cai_em_todas(client, db):
    cria_unidade(db, 'Unidade Qualquer', '10000000000930')
    db.session.commit()
    _login(client)

    resposta = client.get('/raizen?filtro=lixo')
    assert resposta.status_code == 200
    assert 'Unidade Qualquer' in resposta.get_data(as_text=True)


def test_raizen_modal_lancar_pedido_lista_todas_unidades_mesmo_com_filtro_ativo(client, db):
    """O select do modal 'Lançar Pedido' não pode ficar restrito às unidades
    visíveis no filtro — senão não dá pra lançar pedido pra quem sumiu da tela."""
    com_pedido = cria_unidade(db, 'Unidade Visivel No Filtro', '10000000001011')
    cria_pedido(db, com_pedido, status='Pendente')
    fora_do_filtro = cria_unidade(db, 'Unidade Fora Do Filtro', '10000000001092')
    db.session.commit()
    _login(client)

    resposta = client.get('/raizen?filtro=pedidos')
    corpo = resposta.get_data(as_text=True)
    # A unidade sem pedido pendente não aparece como card, mas precisa
    # continuar como opção no <select> do modal de lançar pedido.
    assert f'value="{fora_do_filtro.id}">Unidade Fora Do Filtro' in corpo


# --- /unidade/<id> (detalhe) ---

def test_detalhe_unidade_sem_filtro_mostra_pedidos_e_propostas(client, db):
    cnpj = '10000000001173'
    unidade = cria_unidade(db, 'Unidade Detalhe', cnpj)
    cria_pedido(db, unidade, status='Pendente')
    cliente = cria_cliente(db, cnpj=cnpj, razao_social='Cliente Detalhe LTDA')
    cria_proposta(db, cliente, status_cobranca='Pendente')
    db.session.commit()
    _login(client)

    resposta = client.get(f'/unidade/{unidade.id}')
    corpo = resposta.get_data(as_text=True)
    assert 'Precisa de Ação' in corpo
    assert 'Propostas' in corpo


def test_detalhe_unidade_filtro_pedidos_esconde_propostas(client, db):
    cnpj = '10000000001254'
    unidade = cria_unidade(db, 'Unidade Filtro Pedidos', cnpj)
    cria_pedido(db, unidade, status='Pendente')
    cliente = cria_cliente(db, cnpj=cnpj, razao_social='Cliente Filtro Pedidos LTDA')
    cria_proposta(db, cliente, status_cobranca='Pendente')
    db.session.commit()
    _login(client)

    resposta = client.get(f'/unidade/{unidade.id}?filtro=pedidos')
    corpo = resposta.get_data(as_text=True)
    assert 'Precisa de Ação' in corpo
    assert '💰 Propostas' not in corpo


def test_detalhe_unidade_filtro_propostas_esconde_pedidos_pendentes(client, db):
    cnpj = '10000000001335'
    unidade = cria_unidade(db, 'Unidade Filtro Propostas', cnpj)
    cria_pedido(db, unidade, status='Pendente')
    cliente = cria_cliente(db, cnpj=cnpj, razao_social='Cliente Filtro Propostas LTDA')
    cria_proposta(db, cliente, status_cobranca='Pendente')
    db.session.commit()
    _login(client)

    resposta = client.get(f'/unidade/{unidade.id}?filtro=propostas')
    corpo = resposta.get_data(as_text=True)
    assert '⚠️ Precisa de Ação' not in corpo
    assert '💰 Propostas' in corpo


def test_detalhe_unidade_filtro_ambos_mostra_as_duas_secoes(client, db):
    cnpj = '10000000001416'
    unidade = cria_unidade(db, 'Unidade Filtro Ambos', cnpj)
    cria_pedido(db, unidade, status='Pendente')
    cliente = cria_cliente(db, cnpj=cnpj, razao_social='Cliente Filtro Ambos LTDA')
    cria_proposta(db, cliente, status_cobranca='Pendente')
    db.session.commit()
    _login(client)

    resposta = client.get(f'/unidade/{unidade.id}?filtro=ambos')
    corpo = resposta.get_data(as_text=True)
    assert '⚠️ Precisa de Ação' in corpo
    assert '💰 Propostas' in corpo


def test_detalhe_unidade_aguardando_retorno_sempre_visivel_mesmo_com_filtro(client, db):
    """Pedido já 'Cobrado' não é 'pendência' no sentido do filtro — a seção
    Aguardando Retorno não deve ser afetada por filtro=pedidos/propostas."""
    unidade = cria_unidade(db, 'Unidade Aguardando', '10000000001497')
    cria_pedido(db, unidade, status='Cobrado')
    db.session.commit()
    _login(client)

    resposta = client.get(f'/unidade/{unidade.id}?filtro=propostas')
    corpo = resposta.get_data(as_text=True)
    assert 'Aguardando Retorno' in corpo
