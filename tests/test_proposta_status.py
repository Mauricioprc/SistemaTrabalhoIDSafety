"""dias_parado precisa resetar quando o status da proposta muda — antes
contava sempre a partir de data_criacao_proposta, então uma proposta que
mudava de status continuava acumulando dias como se nunca tivesse sido
tocada. Também cobre a remoção do status "Negociando": só Pendente/Ok são
aceitos agora (validação no model e nas rotas)."""
import pytest

from app.extensions import db
from app.models import Proposta
from tests.conftest import cria_cliente, cria_proposta, dias_atras


def test_dias_parado_usa_data_criacao_quando_nunca_mudou_de_status(db):
    cliente = cria_cliente(db, cnpj='50000000000191')
    proposta = cria_proposta(db, cliente, status_cobranca='Pendente',
                              data_criacao_proposta=dias_atras(20))
    db.session.commit()

    assert proposta.data_ultima_mudanca_status is None
    assert proposta.dias_parado == 20


def test_dias_parado_reseta_quando_data_ultima_mudanca_status_e_atualizada(db):
    """Simula o que marcar_status_proposta faz: muda o status e marca
    data_ultima_mudanca_status = agora. dias_parado deve passar a contar
    daqui, não mais da criação."""
    cliente = cria_cliente(db, cnpj='50000000000272')
    proposta = cria_proposta(db, cliente, status_cobranca='Pendente',
                              data_criacao_proposta=dias_atras(30))
    db.session.commit()
    assert proposta.dias_parado == 30  # antes de mudar, conta da criação

    from datetime import datetime
    proposta.status_cobranca = 'Ok'
    proposta.data_ultima_mudanca_status = datetime.utcnow()
    db.session.commit()

    assert proposta.dias_parado == 0  # resetou, não continua em 30


def test_marcar_status_proposta_seta_data_ultima_mudanca_status(client, db):
    """Round-trip pela rota real (app/routes/cobranca.py)."""
    cliente = cria_cliente(db, cnpj='50000000000353')
    proposta = cria_proposta(db, cliente, status_cobranca='Pendente',
                              data_criacao_proposta=dias_atras(45))
    db.session.commit()
    proposta_id = proposta.id

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.post(f'/proposta/{proposta_id}/status/Ok', follow_redirects=True)
    assert resposta.status_code == 200

    atualizada = db.session.get(Proposta, proposta_id)
    assert atualizada.status_cobranca == 'Ok'
    assert atualizada.data_ultima_mudanca_status is not None
    assert atualizada.dias_parado == 0


def test_marcar_status_propostas_lote_seta_data_ultima_mudanca_status(client, db):
    cliente = cria_cliente(db, cnpj='50000000000434')
    p1 = cria_proposta(db, cliente, numero_proposta='L1', status_cobranca='Pendente',
                        data_criacao_proposta=dias_atras(60))
    p2 = cria_proposta(db, cliente, numero_proposta='L2', status_cobranca='Pendente',
                        data_criacao_proposta=dias_atras(60))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.post(f'/cliente/{cliente.id}/propostas/status/Ok', follow_redirects=True)
    assert resposta.status_code == 200

    for proposta_id in (p1.id, p2.id):
        atualizada = db.session.get(Proposta, proposta_id)
        assert atualizada.status_cobranca == 'Ok'
        assert atualizada.data_ultima_mudanca_status is not None
        assert atualizada.dias_parado == 0


def test_model_rejeita_status_negociando(db):
    cliente = cria_cliente(db, cnpj='50000000000515')
    proposta = cria_proposta(db, cliente, status_cobranca='Pendente')
    db.session.commit()

    with pytest.raises(ValueError):
        proposta.status_cobranca = 'Negociando'


def test_rota_marcar_status_proposta_rejeita_status_invalido(client, db):
    cliente = cria_cliente(db, cnpj='50000000000606')
    proposta = cria_proposta(db, cliente, status_cobranca='Pendente')
    db.session.commit()
    proposta_id = proposta.id

    with client.session_transaction() as sess:
        sess['autenticado'] = True

    resposta = client.post(f'/proposta/{proposta_id}/status/Negociando', follow_redirects=True)
    assert resposta.status_code == 200

    inalterada = db.session.get(Proposta, proposta_id)
    assert inalterada.status_cobranca == 'Pendente'
    assert inalterada.data_ultima_mudanca_status is None
