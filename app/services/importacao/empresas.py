from datetime import datetime

from app.extensions import db
from app.models import Cliente
from app.services.importacao.base import ImportadorBase
from app.services.importacao.parsing import campo, cnpj_limpo


class EmpresasImportador(ImportadorBase):
    """Cadastro de clientes (dados cadastrais/comerciais base)."""
    nome_fonte = 'Empresas'

    def validar(self, linha: dict) -> list:
        erros = []
        if not cnpj_limpo(linha, 'Cnpj/Cpf'):
            erros.append('CNPJ/CPF vazio ou inválido')
        if not campo(linha, 'Razão Social'):
            erros.append('Razão Social vazia')
        return erros

    def aplicar(self, linha: dict) -> None:
        cnpj = cnpj_limpo(linha, 'Cnpj/Cpf')
        razao = campo(linha, 'Razão Social')
        telefone = campo(linha, 'Celular') or campo(linha, 'Telefone')
        vendedor = campo(linha, 'Representante')
        emails = (campo(linha, 'E-mails Aprovação (Empresa)')
                  or campo(linha, 'E-mails Fatura'))

        cliente = Cliente.query.filter_by(cnpj=cnpj).first()
        if not cliente:
            cliente = Cliente(razao_social=razao, cnpj=cnpj, data_cadastro=datetime.utcnow())
            db.session.add(cliente)

        cliente.razao_social = razao
        cliente.telefone = telefone or cliente.telefone
        cliente.vendedor = vendedor or cliente.vendedor
        cliente.emails_cobranca = emails or cliente.emails_cobranca
        cliente.data_atualizacao = datetime.utcnow()
