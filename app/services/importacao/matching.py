"""Normalização e resolução de Razão Social para o matching da Curva ABC,
que não traz CNPJ — só o texto da razão social."""
import re
import unicodedata

from app.extensions import db
from app.models import Cliente, RazaoSocialAlias

SUFIXOS = (
    r'\bLTDA\b', r'\bEIRELI\b', r'\bS\.?A\.?\b', r'\bS/A\b', r'\bSA\b',
    r'\bME\b', r'\bEPP\b', r'\bMEI\b',
)


def normalizar_razao_social(texto: str) -> str:
    if not texto:
        return ''
    txt = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    txt = txt.upper()
    for sufixo in SUFIXOS:
        txt = re.sub(sufixo, '', txt)
    txt = re.sub(r'[^A-Z0-9 ]', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def resolver_razao_social(razao_social_planilha: str):
    """Tenta casar a razão social da Curva ABC com um Cliente existente.

    Retorna (cliente_ou_none, criou_alias_pendente: bool).
    Se já existir um RazaoSocialAlias para esse texto (resolvido manualmente
    ou não), usa o cliente_id gravado nele.
    """
    alias = RazaoSocialAlias.query.filter_by(razao_social_planilha=razao_social_planilha).first()
    if alias:
        return alias.cliente, False

    normalizada = normalizar_razao_social(razao_social_planilha)
    cliente_encontrado = None
    if normalizada:
        for cliente in Cliente.query.all():
            if normalizar_razao_social(cliente.razao_social) == normalizada:
                cliente_encontrado = cliente
                break

    novo_alias = RazaoSocialAlias(
        razao_social_planilha=razao_social_planilha,
        cliente_id=cliente_encontrado.id if cliente_encontrado else None,
    )
    db.session.add(novo_alias)
    return cliente_encontrado, cliente_encontrado is None
