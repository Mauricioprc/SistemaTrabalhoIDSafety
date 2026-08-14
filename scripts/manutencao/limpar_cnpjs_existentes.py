"""Script de manutenção — execução única e manual, não roda automaticamente
no deploy.

Reaplica limpar_cnpj() (app/utils/formatters.py) sobre Cliente.cnpj já
salvos no banco, garantindo que fiquem só com dígitos (sem pontuação/traço/
barra que possa ter entrado por importação antiga ou edição manual). Não
descarta nem "conserta" CNPJs com menos/mais de 14 dígitos — muitos desses
são CPF de pessoa física (11 dígitos), legítimos — só loga um aviso pra
revisão manual de quem sobrar estranho.

Uso (a partir da raiz do projeto):
    python scripts/manutencao/limpar_cnpjs_existentes.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app
from app.extensions import db
from app.models import Cliente
from app.utils.formatters import limpar_cnpj


def main():
    app = create_app()
    with app.app_context():
        clientes = Cliente.query.all()
        alterados = []
        suspeitos = []

        for cliente in clientes:
            original = cliente.cnpj
            limpo = limpar_cnpj(original)
            if limpo != original:
                cliente.cnpj = limpo
                alterados.append((cliente.id, original, limpo))
            if limpo and len(limpo) != 14:
                suspeitos.append((cliente.id, cliente.razao_social, limpo))

        db.session.commit()

        print(f'\nClientes verificados: {len(clientes)}')
        print(f'CNPJs alterados (tinham caractere não-dígito): {len(alterados)}')
        for cliente_id, original, limpo in alterados[:20]:
            print(f'- cliente_id={cliente_id}: {original!r} -> {limpo!r}')

        print(f'\nCNPJs com != 14 dígitos após limpeza (revisar manualmente '
              f'se não forem CPF de pessoa física, 11 dígitos): {len(suspeitos)}')
        for cliente_id, razao, limpo in suspeitos[:30]:
            print(f'- cliente_id={cliente_id} ({razao}): {len(limpo)} dígitos -> {limpo!r}')


if __name__ == '__main__':
    main()
