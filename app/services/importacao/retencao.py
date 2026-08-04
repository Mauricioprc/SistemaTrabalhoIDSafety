from datetime import datetime

from app.extensions import db
from app.models import Cliente, IndicadorRetencao
from app.services.importacao.base import ImportadorBase
from app.services.importacao.parsing import campo, cnpj_limpo, parse_data_br, parse_percentual


class RetencaoImportador(ImportadorBase):
    """Indicador de retenção — 1 registro por cliente, sobrescrito a cada importação."""
    nome_fonte = 'Retenção'

    def validar(self, linha: dict) -> list:
        erros = []
        if not cnpj_limpo(linha, 'CNPJ/CPF'):
            erros.append('CNPJ/CPF vazio ou inválido')
        return erros

    def aplicar(self, linha: dict) -> None:
        cnpj = cnpj_limpo(linha, 'CNPJ/CPF')
        razao = campo(linha, 'Razão Social')

        cliente = Cliente.query.filter_by(cnpj=cnpj).first()
        if not cliente:
            cliente = Cliente(razao_social=razao, cnpj=cnpj)
            db.session.add(cliente)
            db.session.flush()

        indicador = IndicadorRetencao.query.filter_by(cliente_id=cliente.id).first()
        if not indicador:
            indicador = IndicadorRetencao(cliente_id=cliente.id)
            db.session.add(indicador)

        dias_str = campo(linha, 'Dias Desde o Último Pedido')
        indicador.frequencia_compra = campo(linha, 'Frequência de Compra')
        indicador.classificacao = campo(linha, 'Classificação')
        indicador.dias_desde_ultimo_pedido = int(dias_str) if dias_str.isdigit() else None
        indicador.gauge = campo(linha, 'Gauge')
        indicador.ira_cair = campo(linha, 'Irá Cair?').upper() == 'SIM'
        indicador.previsao_queda = parse_data_br(campo(linha, 'Previsão de Queda'))
        indicador.atualizado_em = datetime.utcnow()
