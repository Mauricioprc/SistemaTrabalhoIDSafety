"""Importadores de Empresas e Propostas — dados sintéticos pequenos, nunca
os CSVs reais de produção."""
import io

from werkzeug.datastructures import FileStorage

from app.models import Cliente, Proposta
from app.services.importacao.empresas import EmpresasImportador
from app.services.importacao.propostas import importar_propostas
from app.services.painel_acao import cliente_novo
from tests.conftest import cria_cliente, dias_atras


def _arquivo(conteudo: str, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(conteudo.encode('utf-8-sig')), filename=filename)


EMPRESAS_HEADER = ('Cnpj/Cpf;Razão Social;Categoria;Representante;Telefone;Celular;'
                    'E-mails Fatura;E-mails Aprovação (Empresa);E-mails Aprovação (Solicitantes)')


def _csv_empresas(linhas):
    return '\n'.join([EMPRESAS_HEADER] + linhas)


def test_import_empresas_cria_cliente_com_data_cadastro(db):
    csv = _csv_empresas(['11111111000191;ACME INDUSTRIA LTDA;B2B;VENDEDOR X;1111111111;2222222222;'
                         'fatura@acme.com;aprov@acme.com;—'])

    resultado = EmpresasImportador().processar(_arquivo(csv, 'empresas.csv'))
    db.session.commit()

    assert resultado.sucesso == 1
    cliente = Cliente.query.filter_by(cnpj='11111111000191').first()
    assert cliente is not None
    assert cliente.razao_social == 'ACME INDUSTRIA LTDA'
    assert cliente.data_cadastro is not None


def test_reimportar_empresas_nao_duplica_nem_sobrescreve_data_cadastro(db):
    csv1 = _csv_empresas(['11111111000191;ACME INDUSTRIA LTDA;B2B;VENDEDOR X;1111111111;2222222222;'
                          'fatura@acme.com;aprov@acme.com;—'])
    EmpresasImportador().processar(_arquivo(csv1, 'empresas.csv'))
    db.session.commit()

    cliente = Cliente.query.filter_by(cnpj='11111111000191').first()
    data_cadastro_original = cliente.data_cadastro

    # Reimporta o mesmo CNPJ com razão social levemente diferente (ex: correção de digitação)
    csv2 = _csv_empresas(['11111111000191;ACME INDUSTRIA LTDA ATUALIZADA;B2B;VENDEDOR Y;3333333333;'
                          '4444444444;fatura@acme.com;aprov2@acme.com;—'])
    EmpresasImportador().processar(_arquivo(csv2, 'empresas.csv'))
    db.session.commit()

    assert Cliente.query.filter_by(cnpj='11111111000191').count() == 1
    cliente_atualizado = Cliente.query.filter_by(cnpj='11111111000191').first()
    assert cliente_atualizado.razao_social == 'ACME INDUSTRIA LTDA ATUALIZADA'
    assert cliente_atualizado.vendedor == 'VENDEDOR Y'
    assert cliente_atualizado.data_cadastro == data_cadastro_original


PROPOSTAS_HEADER = ('Nº Proposta,Cnpj/Cpf,Razão Social,Total,Data Criação,Vendedor,Contato,'
                     'Celular,Telefone,Email Solicit.,Email Aprov.,Email NF')


def _csv_propostas(linhas):
    return '\n'.join([PROPOSTAS_HEADER] + linhas)


def test_import_propostas_cria_atualiza_e_remove(db):
    cria_cliente(db, cnpj='22222222000100', razao_social='BETA LTDA')
    db.session.commit()

    # 1ª importação: cria proposta 1001 e 1002
    csv1 = _csv_propostas([
        '1001,22222222000100,BETA LTDA,"R$ 100,00",01/01/2026 10:00,VEND,Fulano,111,222,a@b.com,c@d.com,e@f.com',
        '1002,22222222000100,BETA LTDA,"R$ 200,00",01/01/2026 10:00,VEND,Fulano,111,222,a@b.com,c@d.com,e@f.com',
    ])
    resultado1 = importar_propostas(_arquivo(csv1, 'propostas.csv'))
    assert resultado1['propostas_novas'] == 2
    assert Proposta.query.count() == 2

    # 2ª importação: 1001 atualizada (valor muda), 1002 some (removida), 1003 é nova
    csv2 = _csv_propostas([
        '1001,22222222000100,BETA LTDA,"R$ 150,00",01/01/2026 10:00,VEND,Fulano,111,222,a@b.com,c@d.com,e@f.com',
        '1003,22222222000100,BETA LTDA,"R$ 300,00",01/01/2026 10:00,VEND,Fulano,111,222,a@b.com,c@d.com,e@f.com',
    ])
    resultado2 = importar_propostas(_arquivo(csv2, 'propostas.csv'))

    assert resultado2['propostas_novas'] == 1
    assert resultado2['propostas_atualizadas'] == 1
    assert resultado2['propostas_removidas'] == 1

    numeros_restantes = {p.numero_proposta for p in Proposta.query.all()}
    assert numeros_restantes == {'1001', '1003'}

    proposta_1001 = Proposta.query.filter_by(numero_proposta='1001').first()
    assert proposta_1001.valor == 150.0


def test_filtro_clientes_novos_respeita_janela_e_data_nula(db):
    recente_sem_proposta = cria_cliente(db, cnpj='30000000000191', data_cadastro=dias_atras(10))
    antigo_sem_proposta = cria_cliente(db, cnpj='30000000000272', data_cadastro=dias_atras(90))
    sem_data_sem_proposta = cria_cliente(db, cnpj='30000000000353', data_cadastro=None)
    db.session.commit()

    assert cliente_novo(recente_sem_proposta) is True
    assert cliente_novo(antigo_sem_proposta) is False
    assert cliente_novo(sem_data_sem_proposta) is False
