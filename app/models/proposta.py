import os
from datetime import datetime

from app.extensions import db


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
    status_cobranca = db.Column(db.String(50), default='Pendente')  # Pendente / Negociando / Ok
    contato = db.Column(db.String(100))
    celular = db.Column(db.String(20))
    telefone = db.Column(db.String(20))
    email_solicit = db.Column(db.String(200))
    email_aprov = db.Column(db.Text)
    email_nf = db.Column(db.Text)
    vendedor = db.Column(db.String(100))
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)

    @property
    def dias_parado(self):
        if not self.data_criacao_proposta:
            return 0
        return (datetime.utcnow() - self.data_criacao_proposta).days
