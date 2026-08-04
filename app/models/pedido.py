import os
from datetime import datetime

from app.extensions import db


class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    arquivo = db.Column(db.String(200), nullable=False)
    data_upload = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Pendente')
    observacao = db.Column(db.Text, nullable=True)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)

    @property
    def numero(self):
        """Número do pedido: nome do PDF sem a extensão (ex: 361114.pdf -> 361114)."""
        return os.path.splitext(self.arquivo)[0]
