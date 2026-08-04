"""
Script de migração única: cria a tabela `proposta` e converte o
`Cliente.valor_pendente` (antigo campo único) em uma Proposta "legada",
para não perder o histórico de dívida já registrado no banco.

Rodar uma vez, ANTES do primeiro deploy do novo app.py:
    python migrar_propostas.py
"""
from app import app, db, Cliente, Proposta

with app.app_context():
    db.create_all()  # cria a tabela proposta se ainda não existir

    clientes = Cliente.query.all()
    migrados = 0
    for cliente in clientes:
        valor_antigo, status_antigo = db.session.execute(
            db.text("SELECT valor_pendente, status_cobranca FROM cliente WHERE id = :id"),
            {"id": cliente.id}
        ).first()

        if not valor_antigo or valor_antigo <= 0:
            continue
        if Proposta.query.filter_by(cliente_id=cliente.id).count() > 0:
            continue

        numero = f'LEGADO-{cliente.id}'
        if Proposta.query.filter_by(numero_proposta=numero).first():
            continue

        db.session.add(Proposta(
            numero_proposta=numero,
            valor=float(valor_antigo),
            status_cobranca='Negociando' if status_antigo == 'Em Negociação' else (status_antigo or 'Pendente'),
            vendedor=cliente.vendedor,
            email_aprov=cliente.emails_cobranca,
            telefone=cliente.telefone,
            cliente_id=cliente.id,
        ))
        migrados += 1

    db.session.commit()
    print(f'Migração concluída. {migrados} propostas legadas criadas.')
