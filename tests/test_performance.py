"""Garante que recalcular_todos() não regride pra N+1: o número de queries
não deve crescer proporcionalmente à quantidade de clientes."""
from sqlalchemy import event

from app.extensions import db
from app.services.priorizacao import recalcular_todos
from tests.conftest import cria_classe_abc, cria_cliente, cria_indicador_retencao, cria_nota_nps, cria_proposta


def test_recalcular_todos_nao_cresce_linearmente_com_clientes(app):
    # Cria clientes com todas as relações que calcular_score() acessa —
    # exatamente o cenário que gerava N+1 antes do eager loading.
    for i in range(15):
        cliente = cria_cliente(db, cnpj=f'9000000000{i:04d}')
        cria_indicador_retencao(db, cliente, ira_cair=True, frequencia_compra='Mensal',
                                 dias_desde_ultimo_pedido=90)
        cria_classe_abc(db, cliente, classe='A')
        cria_nota_nps(db, cliente, nota=5)
        cria_proposta(db, cliente, status_cobranca='Pendente')
    db.session.commit()

    contador = {'n': 0}

    def _on_execute(*args, **kwargs):
        contador['n'] += 1

    event.listen(db.engine, 'before_cursor_execute', _on_execute)
    try:
        recalcular_todos()
    finally:
        event.remove(db.engine, 'before_cursor_execute', _on_execute)

    # 1 query pros clientes + 1 por coleção 1:N (propostas/notas/classes) via
    # selectinload + 1 commit — não uma por cliente. Um N+1 real geraria bem
    # mais de umas poucas dezenas de queries com só 15 clientes (5 relações
    # navegadas por cliente = 75+ queries se não fosse eager loaded).
    assert contador['n'] < 15, f'esperava poucas queries fixas, obteve {contador["n"]} (indício de N+1)'
