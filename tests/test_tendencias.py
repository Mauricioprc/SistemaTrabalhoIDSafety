"""Cliente.tendencia_nps e Cliente.tendencia_classe_abc — comparam os 2
registros mais recentes de cada histórico (notas_nps / classes_abc)."""
from tests.conftest import cria_classe_abc, cria_cliente, cria_nota_nps


# --- tendencia_nps ---

def test_tendencia_nps_none_sem_nenhuma_nota(db):
    cliente = cria_cliente(db, cnpj='60000000000191')
    assert cliente.tendencia_nps is None


def test_tendencia_nps_none_com_apenas_1_nota(db):
    cliente = cria_cliente(db, cnpj='60000000000272')
    cria_nota_nps(db, cliente, nota=8)
    db.session.commit()
    assert cliente.tendencia_nps is None


def test_tendencia_nps_subindo(db):
    cliente = cria_cliente(db, cnpj='60000000000353')
    cria_nota_nps(db, cliente, nota=5)   # mais antiga
    cria_nota_nps(db, cliente, nota=9)   # mais recente
    db.session.commit()
    assert cliente.tendencia_nps == 'subindo'


def test_tendencia_nps_caindo(db):
    cliente = cria_cliente(db, cnpj='60000000000434')
    cria_nota_nps(db, cliente, nota=9)   # mais antiga
    cria_nota_nps(db, cliente, nota=4)   # mais recente
    db.session.commit()
    assert cliente.tendencia_nps == 'caindo'


def test_tendencia_nps_estavel(db):
    cliente = cria_cliente(db, cnpj='60000000000515')
    cria_nota_nps(db, cliente, nota=7)
    cria_nota_nps(db, cliente, nota=7)
    db.session.commit()
    assert cliente.tendencia_nps == 'estavel'


def test_tendencia_nps_usa_so_as_2_mais_recentes(db):
    """Com 3+ notas, só as 2 últimas importam pra tendência."""
    cliente = cria_cliente(db, cnpj='60000000000606')
    cria_nota_nps(db, cliente, nota=1)   # bem antiga — não deveria influenciar
    cria_nota_nps(db, cliente, nota=9)   # penúltima
    cria_nota_nps(db, cliente, nota=9)   # mais recente
    db.session.commit()
    assert cliente.tendencia_nps == 'estavel'


# --- tendencia_classe_abc ---

def test_tendencia_classe_abc_none_sem_nenhuma_classificacao(db):
    cliente = cria_cliente(db, cnpj='60000000000697')
    assert cliente.tendencia_classe_abc is None


def test_tendencia_classe_abc_none_com_apenas_1_classificacao(db):
    cliente = cria_cliente(db, cnpj='60000000000778')
    cria_classe_abc(db, cliente, classe='B', trimestre_referencia='2026-Q3')
    db.session.commit()
    assert cliente.tendencia_classe_abc is None


def test_tendencia_classe_abc_subindo(db):
    cliente = cria_cliente(db, cnpj='60000000000859')
    cria_classe_abc(db, cliente, classe='C', trimestre_referencia='2026-Q2')
    cria_classe_abc(db, cliente, classe='A', trimestre_referencia='2026-Q3')
    db.session.commit()
    assert cliente.tendencia_classe_abc == 'subindo'


def test_tendencia_classe_abc_caindo(db):
    cliente = cria_cliente(db, cnpj='60000000000930')
    cria_classe_abc(db, cliente, classe='A', trimestre_referencia='2026-Q2')
    cria_classe_abc(db, cliente, classe='C', trimestre_referencia='2026-Q3')
    db.session.commit()
    assert cliente.tendencia_classe_abc == 'caindo'


def test_tendencia_classe_abc_estavel(db):
    cliente = cria_cliente(db, cnpj='60000000001010')
    cria_classe_abc(db, cliente, classe='B', trimestre_referencia='2026-Q2')
    cria_classe_abc(db, cliente, classe='B', trimestre_referencia='2026-Q3')
    db.session.commit()
    assert cliente.tendencia_classe_abc == 'estavel'
