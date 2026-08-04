from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Tarefa

bp = Blueprint('tarefas', __name__)


@bp.route('/tarefas')
def tarefas():
    todo = Tarefa.query.filter_by(status='todo').order_by(Tarefa.prioridade.asc(), Tarefa.data_criacao.desc()).all()
    doing = Tarefa.query.filter_by(status='doing').order_by(Tarefa.data_criacao.desc()).all()
    done = Tarefa.query.filter_by(status='done').order_by(Tarefa.data_criacao.desc()).limit(20).all()
    return render_template('tarefas.html', todo=todo, doing=doing, done=done)


@bp.route('/nova_tarefa', methods=['POST'])
def nova_tarefa():
    titulo = request.form.get('titulo')
    if titulo:
        db.session.add(Tarefa(titulo=titulo, descricao=request.form.get('descricao'),
                               prioridade=request.form.get('prioridade'), status='todo'))
        db.session.commit()
        flash('Tarefa criada!', 'success')
    return redirect(url_for('tarefas.tarefas'))


@bp.route('/mover_tarefa/<int:id>/<status>')
def mover_tarefa(id, status):
    t = Tarefa.query.get(id)
    if t:
        t.status = status
        db.session.commit()
    return redirect(url_for('tarefas.tarefas'))


@bp.route('/excluir_tarefa/<int:id>')
def excluir_tarefa(id):
    t = Tarefa.query.get(id)
    if t:
        db.session.delete(t)
        db.session.commit()
    return redirect(url_for('tarefas.tarefas'))
