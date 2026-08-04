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


def candidatos_para_razao_social(razao_social_planilha: str):
    """Retorna a lista de Cliente cuja razão social normalizada bate com a
    razão social informada (0, 1 ou vários — ambiguidade é real: a mesma
    razão social pode ter múltiplos CNPJs/filiais cadastrados)."""
    normalizada = normalizar_razao_social(razao_social_planilha)
    if not normalizada:
        return []
    return [c for c in Cliente.query.all() if normalizar_razao_social(c.razao_social) == normalizada]


def resolver_razao_social(razao_social_planilha: str):
    """Tenta casar a razão social da Curva ABC com um Cliente existente.

    Retorna (cliente_ou_none, alias). `cliente` só vem preenchido quando há
    exatamente 1 candidato (match automático seguro). Com 0 candidatos o
    alias fica pendente com motivo_pendencia='sem_match'; com 2+ candidatos
    fica pendente com motivo_pendencia='ambiguo' e a lista de candidatos
    salva em candidatos_ambiguos_ids — nenhum dos dois casos escolhe um
    cliente sozinho.

    Se já existir um RazaoSocialAlias para esse texto (resolvido manualmente
    ou não), usa o cliente_id já gravado nele.
    """
    alias = RazaoSocialAlias.query.filter_by(razao_social_planilha=razao_social_planilha).first()
    if alias:
        return alias.cliente, alias

    candidatos = candidatos_para_razao_social(razao_social_planilha)

    if len(candidatos) == 1:
        cliente_encontrado = candidatos[0]
        motivo = None
        candidatos_ids = None
    elif len(candidatos) == 0:
        cliente_encontrado = None
        motivo = 'sem_match'
        candidatos_ids = None
    else:
        cliente_encontrado = None
        motivo = 'ambiguo'
        candidatos_ids = ','.join(str(c.id) for c in candidatos)

    novo_alias = RazaoSocialAlias(
        razao_social_planilha=razao_social_planilha,
        cliente_id=cliente_encontrado.id if cliente_encontrado else None,
        motivo_pendencia=motivo,
        candidatos_ambiguos_ids=candidatos_ids,
    )
    db.session.add(novo_alias)
    return cliente_encontrado, novo_alias
