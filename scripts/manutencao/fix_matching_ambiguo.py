"""Script de correção — execução única e manual.

Antes desta correção, o matching de Curva ABC por razão social
(app/services/importacao/matching.py) pegava silenciosamente o primeiro
Cliente que batesse com a razão social normalizada, mesmo quando existiam
vários candidatos (mesma razão social com CNPJs/filiais diferentes — caso
real confirmado, ex: "BRACELL SP CELULOSE LTDA" tem 5 CNPJs cadastrados).

Este script reaplica a checagem de ambiguidade sobre os aliases já
resolvidos automaticamente e desfaz os que na verdade eram ambíguos:
- zera o cliente_id do alias e marca motivo_pendencia='ambiguo', para que
  a resolução manual apareça na tela /importacao;
- remove o ClasseABC que foi gravado incorretamente para aquele cliente,
  já que a classificação foi atribuída sem certeza.

Aliases que batem em exatamente 1 cliente não são tocados.

Já foi executado uma vez em produção (ver commit "Corrige matching ambiguo
na importacao de Curva ABC") e não deveria ter efeito num banco já corrigido
— mas continua útil como ferramenta de manutenção caso dado antigo seja
reimportado por engano, por isso foi isolado aqui em vez de apagado.

Uso (a partir da raiz do projeto):
    python scripts/manutencao/fix_matching_ambiguo.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app
from app.extensions import db
from app.models import ClasseABC, RazaoSocialAlias
from app.services.importacao.matching import candidatos_para_razao_social
from app.services.priorizacao import recalcular_todos


def main():
    app = create_app()
    with app.app_context():
        aliases_automaticos = RazaoSocialAlias.query.filter_by(resolvido_manualmente=False).filter(
            RazaoSocialAlias.cliente_id.isnot(None)).all()

        revertidos = []

        for alias in aliases_automaticos:
            candidatos = candidatos_para_razao_social(alias.razao_social_planilha)
            if len(candidatos) < 2:
                continue  # match de 1 candidato só: continua correto, não mexe

            cliente_id_incorreto = alias.cliente_id

            classe_abc_incorreta = ClasseABC.query.filter_by(cliente_id=cliente_id_incorreto).all()
            for classe_abc in classe_abc_incorreta:
                db.session.delete(classe_abc)

            alias.cliente_id = None
            alias.motivo_pendencia = 'ambiguo'
            alias.candidatos_ambiguos_ids = ','.join(str(c.id) for c in candidatos)

            revertidos.append((alias.razao_social_planilha, cliente_id_incorreto, len(classe_abc_incorreta)))

        db.session.commit()
        recalcular_todos()

        print(f'\nRevertidos: {len(revertidos)} alias(es) com match ambíguo.\n')
        if revertidos:
            print('Razão social | cliente_id incorreto removido | ClasseABC apagados')
            for razao, cliente_id, qtd_classe_abc in revertidos:
                print(f'- {razao} | cliente_id={cliente_id} | {qtd_classe_abc} ClasseABC removido(s)')
            print('\nRevise essas razões sociais manualmente em /importacao.')
        else:
            print('Nenhum match automático ambíguo encontrado no banco.')


if __name__ == '__main__':
    main()
