"""Fixtures compartilhadas — banco de teste sempre em SQLite em memória,
nunca o raizen_gestao.db de desenvolvimento."""
import os
from datetime import datetime, timedelta

import pytest

# create_app() exige SECRET_KEY (ou FLASK_DEBUG=1) — ver app/__init__.py.
# setdefault: não pisa em valores reais se o ambiente já tiver algo definido.
os.environ.setdefault('SECRET_KEY', 'chave-de-teste-nao-usar-em-producao')
os.environ.setdefault('AUTH_USER', 'teste')
os.environ.setdefault('AUTH_PASSWORD', 'teste')

from app import create_app
from app.extensions import db as _db
from app.models import Cliente, ClasseABC, IndicadorRetencao, NotaNPS, Proposta


@pytest.fixture()
def app():
    # A URI precisa ir em config_overrides (aplicado ANTES de db.init_app
    # dentro de create_app) — sobrescrever app.config depois de create_app()
    # não isola nada, o Flask-SQLAlchemy já capturou a URI real. Isso já
    # causou perda de dados do banco de dev uma vez; o assert abaixo é uma
    # trava extra pra nunca mais rodar create_all/drop_all contra o arquivo
    # de verdade por engano.
    application = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',  # em memória — isolado do banco real
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
    })
    assert application.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite://', \
        'Fixture de teste não pode apontar para um arquivo de banco real!'

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


def cria_cliente(db, cnpj, razao_social='CLIENTE TESTE LTDA', **kwargs):
    cliente = Cliente(cnpj=cnpj, razao_social=razao_social, **kwargs)
    db.session.add(cliente)
    db.session.flush()
    return cliente


def cria_proposta(db, cliente, numero_proposta=None, status_cobranca='Pendente',
                   data_criacao_proposta=None, valor=100.0):
    proposta = Proposta(
        numero_proposta=numero_proposta or f'P-{cliente.id}-{status_cobranca}',
        valor=valor,
        status_cobranca=status_cobranca,
        data_criacao_proposta=data_criacao_proposta or datetime.utcnow(),
        cliente_id=cliente.id,
    )
    db.session.add(proposta)
    db.session.flush()
    return proposta


def cria_indicador_retencao(db, cliente, frequencia_compra='Mensal', dias_desde_ultimo_pedido=0,
                             ira_cair=False, **kwargs):
    indicador = IndicadorRetencao(
        cliente_id=cliente.id,
        frequencia_compra=frequencia_compra,
        dias_desde_ultimo_pedido=dias_desde_ultimo_pedido,
        ira_cair=ira_cair,
        **kwargs,
    )
    db.session.add(indicador)
    db.session.flush()
    return indicador


def cria_nota_nps(db, cliente, nota, importado_em=None):
    nota_obj = NotaNPS(cliente_id=cliente.id, nota=nota, importado_em=importado_em or datetime.utcnow())
    db.session.add(nota_obj)
    db.session.flush()
    return nota_obj


def cria_classe_abc(db, cliente, classe='A', trimestre_referencia='2026-Q3'):
    classe_abc = ClasseABC(cliente_id=cliente.id, classe=classe, trimestre_referencia=trimestre_referencia,
                            total_vendas=1000.0, percentual_individual=1.0, percentual_acumulado=1.0)
    db.session.add(classe_abc)
    db.session.flush()
    return classe_abc


def dias_atras(n):
    return datetime.utcnow() - timedelta(days=n)
