from datetime import datetime

from app.extensions import db


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(20), unique=True)
    emails_cobranca = db.Column(db.Text)
    telefone = db.Column(db.String(50))
    vendedor = db.Column(db.String(100))
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)

    # Derivado pelo services/priorizacao.py a cada importação — não é fonte de verdade.
    score_prioridade = db.Column(db.Integer, default=0)
    motivo_prioridade = db.Column(db.Text)

    propostas = db.relationship('Proposta', backref='cliente', lazy=True, cascade="all, delete-orphan")
    indicador_retencao = db.relationship('IndicadorRetencao', backref='cliente', lazy=True,
                                          uselist=False, cascade="all, delete-orphan")
    notas_nps = db.relationship('NotaNPS', backref='cliente', lazy=True,
                                 cascade="all, delete-orphan", order_by='NotaNPS.importado_em.desc()')
    classes_abc = db.relationship('ClasseABC', backref='cliente', lazy=True,
                                   cascade="all, delete-orphan",
                                   order_by='ClasseABC.trimestre_referencia.desc()')

    @property
    def status_cobranca(self):
        """Calculado a partir das propostas: Pendente > Negociando > Ok."""
        if any(p.status_cobranca == 'Pendente' for p in self.propostas):
            return 'Pendente'
        if any(p.status_cobranca == 'Negociando' for p in self.propostas):
            return 'Negociando'
        return 'Ok'

    @property
    def valor_pendente(self):
        return sum(p.valor for p in self.propostas if p.status_cobranca == 'Pendente')

    @property
    def valor_negociando(self):
        return sum(p.valor for p in self.propostas if p.status_cobranca == 'Negociando')

    @property
    def dias_parado_maximo(self):
        pendentes = [p.dias_parado for p in self.propostas if p.status_cobranca == 'Pendente']
        return max(pendentes) if pendentes else 0

    @property
    def qtd_pendentes(self):
        return sum(1 for p in self.propostas if p.status_cobranca == 'Pendente')

    @property
    def classe_abc_atual(self):
        return self.classes_abc[0] if self.classes_abc else None

    @property
    def nota_nps_mais_recente(self):
        return self.notas_nps[0] if self.notas_nps else None


class Contato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(50))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
