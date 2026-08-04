from app.extensions import db
from app.models import Cliente, NotaNPS
from app.services.importacao.base import ImportadorBase
from app.services.importacao.parsing import campo, cnpj_limpo


class NPSImportador(ImportadorBase):
    """Notas de NPS — histórico acumulado, nunca sobrescreve registros anteriores."""
    nome_fonte = 'NPS'

    def validar(self, linha: dict) -> list:
        erros = []
        if not cnpj_limpo(linha, 'Cnpj/Cpf'):
            erros.append('CNPJ/CPF vazio ou inválido')
        nota = campo(linha, 'Nota')
        if not nota or not nota.lstrip('-').isdigit():
            erros.append('Nota inválida')
        return erros

    def aplicar(self, linha: dict) -> None:
        cnpj = cnpj_limpo(linha, 'Cnpj/Cpf')
        razao = campo(linha, 'Empresa')

        cliente = Cliente.query.filter_by(cnpj=cnpj).first()
        if not cliente:
            cliente = Cliente(razao_social=razao, cnpj=cnpj)
            db.session.add(cliente)
            db.session.flush()

        db.session.add(NotaNPS(
            cliente_id=cliente.id,
            nota=int(campo(linha, 'Nota')),
            comentario=campo(linha, 'Comentário') or None,
        ))
