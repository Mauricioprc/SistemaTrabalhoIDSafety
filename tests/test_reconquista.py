"""Mensagens de reconquista/primeiro contato (services/reconquista.py) — a
contraparte "o que fazer" de cada categoria do Radar, no Cliente 360."""
from app.services.reconquista import (
    contexto_atraso, contexto_cliente_novo, mensagem_primeiro_contato, mensagens_reconquista,
)
from tests.conftest import cria_cliente, cria_indicador_retencao, cria_proposta, dias_atras


# --- contexto_atraso ---

def test_contexto_atraso_none_sem_indicador(db):
    cliente = cria_cliente(db, cnpj='90000000000191')
    db.session.commit()
    assert contexto_atraso(cliente) is None


def test_contexto_atraso_none_dentro_do_esperado(db):
    cliente = cria_cliente(db, cnpj='90000000000272')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=10)
    db.session.commit()
    assert contexto_atraso(cliente) is None


def test_contexto_atraso_sugestao_leve_proximo_do_esperado(db):
    cliente = cria_cliente(db, cnpj='90000000000353')
    # 50/45 = 1.11x — abaixo do limiar de reengajamento (1.3x)
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=50)
    db.session.commit()

    ctx = contexto_atraso(cliente)
    assert ctx['sugestao'] == 'leve'
    assert ctx['dias'] == 50
    assert ctx['esperado'] == 45


def test_contexto_atraso_sugestao_reengajamento(db):
    cliente = cria_cliente(db, cnpj='90000000000434')
    # 65/45 = 1.44x — entre os dois limiares
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=65)
    db.session.commit()

    assert contexto_atraso(cliente)['sugestao'] == 'reengajamento'


def test_contexto_atraso_sugestao_urgente_por_proporcao(db):
    cliente = cria_cliente(db, cnpj='90000000000515')
    # 100/45 = 2.2x — acima do limiar urgente
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=100)
    db.session.commit()

    assert contexto_atraso(cliente)['sugestao'] == 'urgente'


def test_contexto_atraso_sugestao_urgente_por_risco_de_queda_mesmo_com_pouco_atraso(db):
    cliente = cria_cliente(db, cnpj='90000000000606')
    # Só 46/45 = 1.02x, mas ira_cair=True deve forçar 'urgente' de qualquer forma
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=46, ira_cair=True)
    db.session.commit()

    assert contexto_atraso(cliente)['sugestao'] == 'urgente'


# --- mensagens_reconquista: cada texto cita os dados reais do cliente ---

def test_mensagens_reconquista_citam_dados_reais(db):
    cliente = cria_cliente(db, cnpj='90000000000687', razao_social='Fabrica Exemplo LTDA')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=100)
    db.session.commit()

    ctx = contexto_atraso(cliente)
    msgs = mensagens_reconquista(cliente, ctx)

    assert set(msgs.keys()) == {'leve', 'reengajamento', 'urgente'}
    for chave, msg in msgs.items():
        assert 'Fabrica Exemplo LTDA' in msg['corpo']
        assert '100 dias' in msg['corpo']
        assert msg['assunto']
        assert msg['titulo']


def test_mensagem_urgente_menciona_risco_de_queda_quando_ira_cair(db):
    cliente = cria_cliente(db, cnpj='90000000000768', razao_social='Risco LTDA')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=200, ira_cair=True)
    db.session.commit()

    ctx = contexto_atraso(cliente)
    msgs = mensagens_reconquista(cliente, ctx)
    assert 'risco real' in msgs['urgente']['corpo']


def test_mensagem_urgente_nao_menciona_risco_quando_ira_cair_false(db):
    cliente = cria_cliente(db, cnpj='90000000000849', razao_social='Sem Risco LTDA')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=200, ira_cair=False)
    db.session.commit()

    ctx = contexto_atraso(cliente)
    msgs = mensagens_reconquista(cliente, ctx)
    assert 'risco real' not in msgs['urgente']['corpo']


# --- contexto_cliente_novo / mensagem_primeiro_contato ---

def test_contexto_cliente_novo_none_se_ja_tem_proposta(db):
    cliente = cria_cliente(db, cnpj='90000000000930', data_cadastro=dias_atras(5))
    cria_proposta(db, cliente, status_cobranca='Pendente', data_criacao_proposta=dias_atras(1))
    db.session.commit()
    assert contexto_cliente_novo(cliente) is None


def test_contexto_cliente_novo_calcula_dias_desde_cadastro(db):
    cliente = cria_cliente(db, cnpj='90000000001011', data_cadastro=dias_atras(7))
    db.session.commit()

    ctx = contexto_cliente_novo(cliente)
    assert ctx['dias_desde_cadastro'] == 7


def test_mensagem_primeiro_contato_cita_nome_e_dias(db):
    cliente = cria_cliente(db, cnpj='90000000001092', razao_social='Novata LTDA', data_cadastro=dias_atras(3))
    db.session.commit()

    ctx = contexto_cliente_novo(cliente)
    msg = mensagem_primeiro_contato(cliente, ctx)
    assert 'Novata LTDA' in msg['corpo']
    assert 'há 3 dias' in msg['corpo']


# --- rota /cliente/<id>: HTML escapa corretamente e mostra o bloco certo ---

def test_rota_cliente_mostra_bloco_reconquista_quando_sem_comprar(client, db):
    cliente = cria_cliente(db, cnpj='90000000001173', razao_social='Cliente Radar LTDA')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=100)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}')
    corpo = resposta.get_data(as_text=True)
    assert 'Cliente sem comprar' in corpo
    assert 'Risco de perda' in corpo  # urgente, pois 100/45 = 2.2x


def test_rota_cliente_escapa_razao_social_no_bloco_de_reconquista(client, db):
    cliente = cria_cliente(db, cnpj='90000000001254', razao_social='Cia <script>alert(1)</script>')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=100)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}')
    corpo = resposta.get_data(as_text=True)
    assert '<script>alert(1)</script>' not in corpo


def test_rota_cliente_quebra_de_linha_vira_br_real_nao_escapado(client, db):
    """Regressão: `corpo | e | replace('\\n', '<br>') | safe` no template
    escapava o <br> de novo (o filtro `replace` do Jinja, operando sobre uma
    string já escapada, escapa a substituição também) — o texto aparecia
    tudo junto, com "&lt;br&gt;" literal na tela. Corrigido gerando o HTML
    pronto em Python (corpo_html, ver services/reconquista._para_html)."""
    cliente = cria_cliente(db, cnpj='90000000001335', razao_social='Cliente Quebra LTDA')
    cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=100)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.get(f'/cliente/{cliente.id}')
    corpo = resposta.get_data(as_text=True)
    inicio = corpo.find('id="reconq_leve"')
    trecho = corpo[inicio:inicio + 500]
    assert '&lt;br&gt;' not in trecho
    assert '<br>' in trecho
