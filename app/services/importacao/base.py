"""Interface comum para importadores de CSV.

Cada fonte de dados (Propostas, Retenção, NPS, Curva ABC, Empresas) implementa
um Importador com os mesmos três métodos, para que o fluxo de upload /
validação / relatório de erro seja único (ver routes/importacao.py).
"""
import csv
import io
from dataclasses import dataclass, field


@dataclass
class ResultadoImportacao:
    nome_fonte: str
    total_linhas: int = 0
    sucesso: int = 0
    erros: list = field(default_factory=list)   # list[(linha_num, [mensagens])]
    extra: dict = field(default_factory=dict)   # estatísticas específicas do importador

    @property
    def qtd_erros(self):
        return len(self.erros)


class ImportadorBase:
    """Cada subclasse implementa ler/validar/aplicar. O restante do fluxo
    (contagem, coleta de erros, commit) é feito por `processar`, que é comum
    a todos os importadores."""

    nome_fonte = "fonte"
    delimitador = ';'

    def ler(self, arquivo) -> list:
        """Lê o arquivo e devolve uma lista de dicts (uma por linha do CSV)."""
        conteudo = arquivo.read()
        if isinstance(conteudo, bytes):
            conteudo = conteudo.decode('utf-8-sig')
        leitor = csv.DictReader(io.StringIO(conteudo), delimiter=self.delimitador)
        return [{(k or '').strip(): v for k, v in linha.items()} for linha in leitor]

    def validar(self, linha: dict) -> list:
        """Retorna lista de mensagens de erro; lista vazia = linha válida."""
        raise NotImplementedError

    def aplicar(self, linha: dict) -> None:
        """Persiste (cria/atualiza) os dados da linha já validada."""
        raise NotImplementedError

    def processar(self, arquivo) -> ResultadoImportacao:
        resultado = ResultadoImportacao(nome_fonte=self.nome_fonte)
        linhas = self.ler(arquivo)
        resultado.total_linhas = len(linhas)
        for i, linha in enumerate(linhas, start=2):  # linha 1 = cabeçalho
            erros_linha = self.validar(linha)
            if erros_linha:
                resultado.erros.append((i, erros_linha))
                continue
            self.aplicar(linha)
            resultado.sucesso += 1
        return resultado
