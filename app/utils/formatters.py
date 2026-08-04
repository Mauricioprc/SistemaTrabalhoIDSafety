import re


def limpar_input(texto):
    if not texto:
        return ""
    return re.sub(r'\D', '', str(texto))


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
