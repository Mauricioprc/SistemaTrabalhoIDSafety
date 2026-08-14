import logging
import re

logger = logging.getLogger(__name__)


def limpar_input(texto):
    if not texto:
        return ""
    return re.sub(r'\D', '', str(texto))


def limpar_cnpj(valor):
    """Remove tudo que não é dígito. Não descarta o dado se o resultado não
    tiver 14 dígitos (CNPJ incompleto/CPF/lixo de planilha) — só sinaliza
    via log, pra quem for gravar o dado decidir o que fazer. Usar sempre que
    for GRAVAR Cliente.cnpj/Proposta — a formatação com pontuação é só na
    exibição, via o filtro Jinja 'cnpj' (formatar_cnpj)."""
    limpo = limpar_input(valor)
    if limpo and len(limpo) != 14:
        logger.warning('CNPJ com %d dígitos após limpeza (esperado 14): valor original=%r, limpo=%r',
                        len(limpo), valor, limpo)
    return limpo


def formatar_cnpj(valor):
    if not valor or len(valor) != 14:
        return valor
    return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"


def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def link_whatsapp(telefone):
    digits = re.sub(r'\D', '', telefone or '')
    if not digits:
        return ''
    if not digits.startswith('55'):
        digits = '55' + digits
    return f'https://wa.me/{digits}'
