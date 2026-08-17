"""Botão 'Voltar' do Cliente 360 (app/routes/clientes._resolver_voltar) —
tinha um link fixo pro Painel de Ação, então vindo do Radar ele levava o
usuário pro lugar errado. Agora respeita de onde a navegação veio."""
from tests.conftest import cria_cliente


def test_voltar_para_radar_quando_referer_e_radar(client, db):
    cliente = cria_cliente(db, cnpj='60000000000191')
    db.session.commit()
    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}', headers={'Referer': 'http://localhost/radar?q=abc'})
    corpo = resposta.get_data(as_text=True)
    assert 'Voltar para o Radar' in corpo
    assert 'href="/radar"' in corpo


def test_voltar_para_clientes_quando_referer_e_clientes(client, db):
    cliente = cria_cliente(db, cnpj='60000000000272')
    db.session.commit()
    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}', headers={'Referer': 'http://localhost/clientes?q=abc'})
    corpo = resposta.get_data(as_text=True)
    assert 'Voltar para Clientes' in corpo
    assert 'href="/clientes"' in corpo


def test_voltar_para_raizen_quando_referer_e_raizen(client, db):
    cliente = cria_cliente(db, cnpj='60000000000353')
    db.session.commit()
    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}', headers={'Referer': 'http://localhost/raizen/42'})
    corpo = resposta.get_data(as_text=True)
    assert 'Voltar para Raízen' in corpo


def test_voltar_para_painel_de_acao_quando_referer_e_cobranca(client, db):
    cliente = cria_cliente(db, cnpj='60000000000434')
    db.session.commit()
    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}', headers={'Referer': 'http://localhost/cobranca?filtro=critico'})
    corpo = resposta.get_data(as_text=True)
    assert 'Voltar para o Painel de ação' in corpo


def test_voltar_cai_no_painel_de_acao_sem_referer(client, db):
    """Acesso direto pela URL (sem referrer) — fallback seguro pra home do sistema."""
    cliente = cria_cliente(db, cnpj='60000000000515')
    db.session.commit()
    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}')
    corpo = resposta.get_data(as_text=True)
    assert 'Voltar para o Painel de ação' in corpo
    assert 'href="/cobranca"' in corpo
