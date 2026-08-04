from datetime import datetime

from app.extensions import db


class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    prioridade = db.Column(db.String(20), default='Normal')
    status = db.Column(db.String(20), default='todo')
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
