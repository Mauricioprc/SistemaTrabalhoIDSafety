from datetime import datetime

from app.extensions import db
from app.models import ClasseABC
from app.services.importacao.base import ImportadorBase, ResultadoImportacao
from app.services.importacao.matching import construir_indice_clientes, resolver_razao_social
from app.services.importacao.parsing import campo, parse_percentual, parse_valor_brl


def trimestre_atual() -> str:
    hoje = datetime.utcnow()
    trimestre = (hoje.month - 1) // 3 + 1
    return f'{hoje.year}-Q{trimestre}'


class CurvaABCImportador(ImportadorBase):
    """Classificação ABC por razão social (sem CNPJ) — usa matching.py para
    tentar casar automaticamente com um Cliente existente. Quando não casa,
    fica pendente em RazaoSocialAlias para resolução manual na tela de
    importação."""
    nome_fonte = 'Curva ABC'

    def validar(self, linha: dict) -> list:
        erros = []
        if not campo(linha, 'Razão Social'):
            erros.append('Razão Social vazia')
        if not campo(linha, 'Classe'):
            erros.append('Classe vazia')
        return erros

    def aplicar(self, linha: dict) -> None:
        raise NotImplementedError('CurvaABCImportador usa processar() customizado')

    def processar(self, arquivo) -> ResultadoImportacao:
        resultado = ResultadoImportacao(nome_fonte=self.nome_fonte)
        linhas = self.ler(arquivo)
        resultado.total_linhas = len(linhas)
        trimestre = trimestre_atual()
        casados = 0
        sem_match = 0

        # Pré-carrega e normaliza todos os Cliente uma única vez, fora do
        # loop de linhas — ver comentário em matching.construir_indice_clientes.
        indice_clientes = construir_indice_clientes()

        for i, linha in enumerate(linhas, start=2):
            erros_linha = self.validar(linha)
            if erros_linha:
                resultado.erros.append((i, erros_linha))
                continue

            razao = campo(linha, 'Razão Social')
            cliente, alias = resolver_razao_social(razao, indice=indice_clientes)

            classe = campo(linha, 'Classe')
            total_vendas = parse_valor_brl(campo(linha, 'Total Vendas'))
            percentual_individual = parse_percentual(campo(linha, '% Individual'))
            percentual_acumulado = parse_percentual(campo(linha, '% Acumulado'))

            if cliente:
                classe_abc = ClasseABC.query.filter_by(
                    cliente_id=cliente.id, trimestre_referencia=trimestre).first()
                if not classe_abc:
                    classe_abc = ClasseABC(cliente_id=cliente.id, trimestre_referencia=trimestre)
                    db.session.add(classe_abc)
                classe_abc.classe = classe
                classe_abc.total_vendas = total_vendas
                classe_abc.percentual_individual = percentual_individual
                classe_abc.percentual_acumulado = percentual_acumulado
                casados += 1
            else:
                if alias:
                    alias.classe_pendente = classe
                    alias.total_vendas_pendente = total_vendas
                    alias.percentual_individual_pendente = percentual_individual
                    alias.percentual_acumulado_pendente = percentual_acumulado
                    alias.trimestre_referencia_pendente = trimestre
                sem_match += 1

            resultado.sucesso += 1

        resultado.extra['trimestre_referencia'] = trimestre
        resultado.extra['casados_automaticamente'] = casados
        resultado.extra['sem_match'] = sem_match
        return resultado
