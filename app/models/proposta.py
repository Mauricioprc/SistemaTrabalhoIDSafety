from datetime import datetime

from sqlalchemy.orm import validates

from app.extensions import db

STATUS_COBRANCA_VALIDOS = ('Pendente', 'Ok')


class Unidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cidade = db.Column(db.String(100))
    cnpj = db.Column(db.String(20))
    contato = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    pedidos = db.relationship('Pedido', backref='unidade', lazy=True, cascade="all, delete-orphan")
    contatos_lista = db.relationship('Contato', backref='unidade', lazy=True, cascade="all, delete-orphan")


class Proposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_proposta = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Float, default=0.0)
    data_criacao_proposta = db.Column(db.DateTime)
    status_cobranca = db.Column(db.String(50), default='Pendente')  # Pendente / Ok — "Negociando" foi removido
    # Atualizada toda vez que status_cobranca muda (ver marcar_status_proposta
    # e marcar_status_propostas_lote em app/routes/cobranca.py). dias_parado
    # conta a partir daqui, não da criação — senão uma proposta que mudou de
    # status continuaria acumulando dias como se nunca tivesse sido tocada.
    data_ultima_mudanca_status = db.Column(db.DateTime, nullable=True)
    contato = db.Column(db.String(100))
    celular = db.Column(db.String(20))
    telefone = db.Column(db.String(20))
    email_solicit = db.Column(db.String(200))
    email_aprov = db.Column(db.Text)
    email_nf = db.Column(db.Text)
    vendedor = db.Column(db.String(100))
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)

    @validates('status_cobranca')
    def _valida_status_cobranca(self, _key, valor):
        if valor not in STATUS_COBRANCA_VALIDOS:
            raise ValueError(f"status_cobranca inválido: {valor!r} (só {STATUS_COBRANCA_VALIDOS})")
        return valor

    @property
    def dias_parado(self):
        referencia = self.data_ultima_mudanca_status or self.data_criacao_proposta
        if not referencia:
            return 0
        return (datetime.utcnow() - referencia).days
