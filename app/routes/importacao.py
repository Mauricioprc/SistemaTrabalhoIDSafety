from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Cliente, ClasseABC, RazaoSocialAlias
from app.services.importacao.curva_abc import CurvaABCImportador
from app.services.importacao.empresas import EmpresasImportador
from app.services.importacao.nps import NPSImportador
from app.services.importacao.retencao import RetencaoImportador
from app.services.priorizacao import recalcular_todos

bp = Blueprint('importacao', __name__)

IMPORTADORES = {
    'retencao': ('Retenção', RetencaoImportador),
    'nps': ('NPS', NPSImportador),
    'curva_abc': ('Curva ABC', CurvaABCImportador),
    'empresas': ('Empresas', EmpresasImportador),
}


@bp.route('/importacao')
def importacao():
    aliases_sem_match = RazaoSocialAlias.query.filter_by(cliente_id=None, motivo_pendencia='sem_match').all()
    aliases_ambiguos = RazaoSocialAlias.query.filter_by(cliente_id=None, motivo_pendencia='ambiguo').all()
    clientes = Cliente.query.order_by(Cliente.razao_social).all()
    return render_template('importacao.html', fontes=IMPORTADORES,
                           aliases_sem_match=aliases_sem_match, aliases_ambiguos=aliases_ambiguos,
                           clientes=clientes)


@bp.route('/importacao/<fonte>', methods=['POST'])
def importar(fonte):
    if fonte not in IMPORTADORES:
        flash('Fonte de importação desconhecida.', 'danger')
        return redirect(url_for('importacao.importacao'))

    nome_fonte, ImportadorClasse = IMPORTADORES[fonte]
    arquivo = request.files.get('arquivo')
    if not arquivo:
        flash('Selecione um arquivo CSV.', 'danger')
        return redirect(url_for('importacao.importacao'))

    try:
        resultado = ImportadorClasse().processar(arquivo)
        db.session.commit()
        recalcular_todos()

        msg = (f'{nome_fonte}: {resultado.total_linhas} linha(s) lidas, '
               f'{resultado.sucesso} processada(s), {resultado.qtd_erros} erro(s).')
        if 'casados_automaticamente' in resultado.extra:
            msg += (f" {resultado.extra['casados_automaticamente']} casado(s) automaticamente, "
                    f"{resultado.extra['sem_match']} sem match (resolução manual necessária).")
        flash(msg, 'success' if resultado.qtd_erros == 0 else 'warning')

        for linha_num, erros in resultado.erros[:20]:
            flash(f'Linha {linha_num}: {", ".join(erros)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao importar {nome_fonte}: {str(e)}', 'danger')

    return redirect(url_for('importacao.importacao'))


@bp.route('/importacao/curva_abc/resolver/<int:alias_id>', methods=['POST'])
def resolver_alias(alias_id):
    alias = RazaoSocialAlias.query.get_or_404(alias_id)
    cliente_id = request.form.get('cliente_id')
    if cliente_id:
        alias.cliente_id = int(cliente_id)
        alias.resolvido_manualmente = True
        alias.motivo_pendencia = None
        alias.candidatos_ambiguos_ids = None

        if alias.trimestre_referencia_pendente:
            classe_abc = ClasseABC.query.filter_by(
                cliente_id=alias.cliente_id,
                trimestre_referencia=alias.trimestre_referencia_pendente).first()
            if not classe_abc:
                classe_abc = ClasseABC(cliente_id=alias.cliente_id,
                                       trimestre_referencia=alias.trimestre_referencia_pendente)
                db.session.add(classe_abc)
            classe_abc.classe = alias.classe_pendente
            classe_abc.total_vendas = alias.total_vendas_pendente
            classe_abc.percentual_individual = alias.percentual_individual_pendente
            classe_abc.percentual_acumulado = alias.percentual_acumulado_pendente

        db.session.commit()
        recalcular_todos()
        flash(f'"{alias.razao_social_planilha}" associado ao cliente selecionado.', 'success')
    return redirect(url_for('importacao.importacao'))
