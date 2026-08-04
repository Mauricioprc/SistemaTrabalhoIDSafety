from datetime import datetime

from app.extensions import db


class IndicadorRetencao(db.Model):
    """1 por Cliente — sobrescrito a cada importação de Retenção."""
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False, unique=True)
    frequencia_compra = db.Column(db.String(30))
    classificacao = db.Column(db.String(30))          # ex: "★★", "Em análise"
    dias_desde_ultimo_pedido = db.Column(db.Integer)
    gauge = db.Column(db.String(20))
    ira_cair = db.Column(db.Boolean, default=False)
    previsao_queda = db.Column(db.Date, nullable=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)


class NotaNPS(db.Model):
    """N por Cliente — histórico acumulado, nunca sobrescreve."""
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    nota = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text, nullable=True)
    importado_em = db.Column(db.DateTime, default=datetime.utcnow)


class ClasseABC(db.Model):
    """1 por Cliente por trimestre."""
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    classe = db.Column(db.String(1))                  # A/B/C
    total_vendas = db.Column(db.Float)
    percentual_individual = db.Column(db.Float)
    percentual_acumulado = db.Column(db.Float)
    trimestre_referencia = db.Column(db.String(10))    # ex: "2026-Q3"

    __table_args__ = (
        db.UniqueConstraint('cliente_id', 'trimestre_referencia', name='uq_classe_abc_cliente_trimestre'),
    )


class RazaoSocialAlias(db.Model):
    """Resolve o problema de Curva ABC não ter CNPJ: guarda a razão social
    exatamente como veio na planilha e o Cliente que ela representa (quando
    já resolvido, seja automaticamente pelo matching ou manualmente)."""
    id = db.Column(db.Integer, primary_key=True)
    razao_social_planilha = db.Column(db.String(200), nullable=False, unique=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    resolvido_manualmente = db.Column(db.Boolean, default=False)

    # Dados da linha da Curva ABC mais recente para essa razão social, mantidos
    # aqui enquanto o alias está pendente para que, ao resolver manualmente,
    # o ClasseABC correspondente possa ser criado sem precisar reimportar.
    classe_pendente = db.Column(db.String(1))
    total_vendas_pendente = db.Column(db.Float)
    percentual_individual_pendente = db.Column(db.Float)
    percentual_acumulado_pendente = db.Column(db.Float)
    trimestre_referencia_pendente = db.Column(db.String(10))

    cliente = db.relationship('Cliente', foreign_keys=[cliente_id])
