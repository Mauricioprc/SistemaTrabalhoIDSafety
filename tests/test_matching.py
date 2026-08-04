"""Matching de razão social da Curva ABC (sem CNPJ na planilha de origem)."""
from app.models import RazaoSocialAlias
from app.services.importacao.matching import normalizar_razao_social, resolver_razao_social
from tests.conftest import cria_cliente


def test_um_candidato_casa_automatico(db):
    cliente = cria_cliente(db, cnpj='11111111000191', razao_social='ACME INDUSTRIA LTDA')

    resultado, alias = resolver_razao_social('ACME INDUSTRIA LTDA')

    assert resultado is not None
    assert resultado.id == cliente.id
    assert alias.cliente_id == cliente.id
    assert alias.motivo_pendencia is None


def test_zero_candidatos_vai_para_fila_sem_match(db):
    resultado, alias = resolver_razao_social('EMPRESA QUE NAO EXISTE NO CADASTRO LTDA')

    assert resultado is None
    assert alias.cliente_id is None
    assert alias.motivo_pendencia == 'sem_match'
    assert alias.candidatos_ambiguos_ids is None


def test_multiplos_candidatos_vai_para_fila_ambiguo(db):
    # Recria o cenário real: mesma razão social, CNPJs (filiais) diferentes.
    c1 = cria_cliente(db, cnpj='53943098000187', razao_social='BRACELL SP CELULOSE LTDA')
    c2 = cria_cliente(db, cnpj='53943098012436', razao_social='BRACELL SP CELULOSE LTDA')
    c3 = cria_cliente(db, cnpj='53943098019104', razao_social='BRACELL SP CELULOSE LTDA')

    resultado, alias = resolver_razao_social('BRACELL SP CELULOSE LTDA')

    assert resultado is None  # nao escolhe nenhum sozinho
    assert alias.cliente_id is None
    assert alias.motivo_pendencia == 'ambiguo'

    ids_candidatos = {int(i) for i in alias.candidatos_ambiguos_ids.split(',')}
    assert ids_candidatos == {c1.id, c2.id, c3.id}

    candidatos_obj = {c.id for c in alias.candidatos_ambiguos}
    assert candidatos_obj == {c1.id, c2.id, c3.id}


def test_alias_ja_resolvido_e_reutilizado_sem_reavaliar(db):
    cliente = cria_cliente(db, cnpj='22222222000100', razao_social='BETA COMERCIO LTDA')
    resolver_razao_social('BETA COMERCIO LTDA')

    # Resolve manualmente para outro cliente qualquer (simula ajuste do usuário)
    outro = cria_cliente(db, cnpj='33333333000100', razao_social='BETA COMERCIO LTDA - FILIAL')
    alias = RazaoSocialAlias.query.filter_by(razao_social_planilha='BETA COMERCIO LTDA').first()
    alias.cliente_id = outro.id
    alias.resolvido_manualmente = True
    db.session.flush()

    resultado, alias_de_novo = resolver_razao_social('BETA COMERCIO LTDA')

    assert resultado.id == outro.id  # usa o que já foi gravado, não reavalia candidatos
    assert cliente.id != outro.id


def test_normalizacao_ignora_caixa_acento_e_sufixo():
    variacoes = [
        'Bracell SP Celulose Ltda',
        'BRACELL SP CELULOSE LTDA',
        'bracell sp celulose ltda',
        'BRACELL SP CELULOSE S.A.',
        'BRACELL SP CELULOSE S/A',
        'BRACELL SP CELULOSE EIRELI',
    ]
    normalizadas = {normalizar_razao_social(v) for v in variacoes}
    assert len(normalizadas) == 1
    assert normalizadas == {'BRACELL SP CELULOSE'}


def test_normalizacao_remove_acentos():
    assert normalizar_razao_social('Raízen Centro-Sul S.A.') == normalizar_razao_social('RAIZEN CENTRO SUL SA')


def test_variacoes_de_caixa_acento_e_sufixo_casam_com_mesmo_cliente(db):
    """Não basta a função de normalização produzir a mesma string — o
    matching de verdade (resolver_razao_social) precisa casar cada variação
    com o mesmo Cliente já cadastrado."""
    cliente = cria_cliente(db, cnpj='44444444000100', razao_social='Bracell SP Celulose Ltda')

    variacoes = [
        'BRACELL SP CELULOSE LTDA',       # caixa alta
        'bracell sp celulose s.a.',       # caixa baixa + sufixo diferente
        'Brácell SP Célulose EIRELI',     # acento + outro sufixo
    ]

    for variacao in variacoes:
        resultado, alias = resolver_razao_social(variacao)
        assert resultado is not None, f'variação "{variacao}" não casou com nenhum cliente'
        assert resultado.id == cliente.id, f'variação "{variacao}" casou com cliente errado'
        assert alias.motivo_pendencia is None
