"""Helpers de parsing compartilhados pelos importadores de CSV."""
from datetime import datetime

from app.utils.formatters import limpar_cnpj

VAZIOS = ('', '—', '-', 'nan', 'none')


def campo(linha: dict, nome: str) -> str:
    valor = linha.get(nome, '')
    if valor is None:
        return ''
    valor = str(valor).strip()
    return '' if valor.lower() in VAZIOS else valor


def cnpj_limpo(linha: dict, nome: str) -> str:
    return limpar_cnpj(campo(linha, nome))


def parse_data_br(valor: str):
    """Datas no formato dd/mm/yyyy vindas das planilhas de Retenção."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor.strip(), '%d/%m/%Y').date()
    except (ValueError, TypeError):
        return None


def parse_percentual(valor: str) -> float:
    if not valor:
        return 0.0
    limpo = valor.replace('%', '').replace(',', '.').strip()
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def parse_valor_brl(valor) -> float:
    if valor is None:
        return 0.0
    limpo = str(valor).replace('R$', '').strip().replace('.', '').replace(',', '.')
    try:
        return float(limpo)
    except (ValueError, TypeError):
        return 0.0
