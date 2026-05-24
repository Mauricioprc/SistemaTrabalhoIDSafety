from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
import os
import re
import pandas as pd
import urllib.parse
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'chave_secreta_raizen_sistema_id'

# --- CONFIGURAÇÃO ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'raizen_gestao.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

PASTA_PDFS = os.path.join(basedir, "static", "pedidos_pdfs")
if not os.path.exists(PASTA_PDFS):
    os.makedirs(PASTA_PDFS)

# --- FILTROS ---
def limpar_input(texto):
    if not texto: return ""
    return re.sub(r'\D', '', str(texto))

def formatar_cnpj(valor):
    if not valor or len(valor) != 14:
        return valor
    return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"

def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

app.jinja_env.filters['cnpj'] = formatar_cnpj
app.jinja_env.filters['moeda'] = formatar_moeda

# --- MODELOS ---

class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    prioridade = db.Column(db.String(20), default='Normal')
    status = db.Column(db.String(20), default='todo')
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

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

class Contato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(50))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    arquivo = db.Column(db.String(200), nullable=False)
    data_upload = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Pendente') 
    observacao = db.Column(db.Text, nullable=True)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(20), unique=True)
    emails_cobranca = db.Column(db.Text) 
    telefone = db.Column(db.String(50))
    vendedor = db.Column(db.String(100))
    valor_pendente = db.Column(db.Float, default=0.0) 
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)
    status_cobranca = db.Column(db.String(50), default='Pendente') 
    observacoes_internas = db.Column(db.Text)

# --- ROTAS GERAIS ---

@app.route('/')
def dashboard():
    total_unidades = Unidade.query.count()
    total_pedidos = Pedido.query.count()
    
    pedidos_pendentes = Pedido.query.filter_by(status='Pendente').count()
    pedidos_cobrados = Pedido.query.filter_by(status='Cobrado').count()
    pedidos_concluidos = Pedido.query.filter_by(status='Concluído').count()
    
    ultimos_pedidos = Pedido.query.order_by(Pedido.data_upload.desc()).limit(5).all()

    total_divida = db.session.query(db.func.sum(Cliente.valor_pendente)).filter(Cliente.status_cobranca != 'Ok').scalar() or 0.0
    qtd_devedores = Cliente.query.filter(Cliente.valor_pendente > 0.01, Cliente.status_cobranca != 'Ok').count()
    maior_devedor = Cliente.query.filter(Cliente.status_cobranca != 'Ok').order_by(Cliente.valor_pendente.desc()).first()
    
    top_devedores = Cliente.query.filter(Cliente.status_cobranca != 'Ok').order_by(Cliente.valor_pendente.desc()).limit(5).all()
    grafico_nomes = [c.razao_social[:15] + '...' for c in top_devedores] 
    grafico_valores = [c.valor_pendente for c in top_devedores]

    tarefas_pendentes = Tarefa.query.filter(Tarefa.status != 'done').count()

    return render_template('dashboard.html', 
                           total_unidades=total_unidades,
                           total_pedidos=total_pedidos,
                           pedidos_pendentes=pedidos_pendentes,
                           pedidos_cobrados=pedidos_cobrados,
                           pedidos_concluidos=pedidos_concluidos,
                           ultimos_pedidos=ultimos_pedidos,
                           total_divida=total_divida,
                           qtd_devedores=qtd_devedores,
                           maior_devedor=maior_devedor,
                           tarefas_pendentes=tarefas_pendentes,
                           grafico_nomes=grafico_nomes,
                           grafico_valores=grafico_valores)

@app.route('/backup')
def backup():
    db_file = os.path.join(basedir, 'raizen_gestao.db')
    if os.path.exists(db_file):
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        nome_arquivo = f'backup_sistema_{data_hoje}.db'
        return send_file(db_file, as_attachment=True, download_name=nome_arquivo)
    else:
        flash('Erro: Banco de dados não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

# --- TAREFAS ---
@app.route('/tarefas')
def tarefas():
    todo = Tarefa.query.filter_by(status='todo').order_by(Tarefa.prioridade.asc(), Tarefa.data_criacao.desc()).all()
    doing = Tarefa.query.filter_by(status='doing').order_by(Tarefa.data_criacao.desc()).all()
    done = Tarefa.query.filter_by(status='done').order_by(Tarefa.data_criacao.desc()).limit(20).all()
    return render_template('tarefas.html', todo=todo, doing=doing, done=done)

@app.route('/nova_tarefa', methods=['POST'])
def nova_tarefa():
    titulo = request.form.get('titulo')
    if titulo:
        db.session.add(Tarefa(titulo=titulo, descricao=request.form.get('descricao'), prioridade=request.form.get('prioridade'), status='todo'))
        db.session.commit(); flash('Tarefa criada!', 'success')
    return redirect(url_for('tarefas'))

@app.route('/mover_tarefa/<int:id>/<status>')
def mover_tarefa(id, status):
    t = Tarefa.query.get(id)
    if t: t.status = status; db.session.commit()
    return redirect(url_for('tarefas'))

@app.route('/excluir_tarefa/<int:id>')
def excluir_tarefa(id):
    t = Tarefa.query.get(id)
    if t: db.session.delete(t); db.session.commit()
    return redirect(url_for('tarefas'))

# --- RAÍZEN ---
@app.route('/raizen')
def raizen():
    q = request.args.get('q', '')
    if q:
        s = f"%{q}%"; l = limpar_input(q)
        unidades = Unidade.query.filter(or_(Unidade.nome.like(s), Unidade.cidade.like(s), Unidade.cnpj.like(l))).all()
    else:
        unidades = Unidade.query.all()
    
    # --- ORDENAÇÃO INTELIGENTE CORRIGIDA ---
    # Prioridade: 
    # 2 = Tem Pendente (Amarelo) -> Fica no Topo
    # 1 = Não tem Pendente, mas tem Cobrado (Azul) -> Fica no Meio
    # 0 = Resto (Cinza) -> Fica no Fim
    
    def get_prioridade(u):
        tem_pendente = any(p.status == 'Pendente' for p in u.pedidos)
        tem_cobrado = any(p.status == 'Cobrado' for p in u.pedidos)
        
        if tem_pendente: return 2
        if tem_cobrado: return 1
        return 0

    # Ordena pela prioridade (maior primeiro) e depois pelo nome
    unidades = sorted(unidades, key=lambda u: (get_prioridade(u), u.nome), reverse=True)
    
    return render_template('raizen.html', unidades=unidades, q=q)

@app.route('/marcar_cobrado/<int:id>')
def marcar_cobrado(id):
    p = Pedido.query.get(id)
    if p: p.status = 'Cobrado'; db.session.commit(); flash('Status: Cobrado.', 'info')
    return redirect(request.referrer or url_for('raizen'))

@app.route('/unidade/<int:id>')
def detalhe_unidade(id):
    u = Unidade.query.get_or_404(id)
    # Listas separadas para o detalhe
    p1 = Pedido.query.filter_by(unidade_id=id, status='Pendente').order_by(Pedido.data_upload.asc()).all()
    p2 = Pedido.query.filter_by(unidade_id=id, status='Cobrado').order_by(Pedido.data_upload.desc()).all()
    p3 = Pedido.query.filter_by(unidade_id=id, status='Concluído').order_by(Pedido.data_upload.desc()).limit(10).all()
    return render_template('detalhe_unidade.html', unidade=u, pendentes=p1, cobrados=p2, concluidos=p3)

@app.route('/criar_unidade', methods=['POST'])
def criar_unidade():
    nome = request.form.get('nome')
    if nome:
        nova = Unidade(nome=nome, cnpj=limpar_input(request.form.get('cnpj')), cidade=request.form.get('cidade'))
        db.session.add(nova); db.session.commit(); flash('Unidade criada!', 'success')
    return redirect(url_for('raizen'))

@app.route('/editar_unidade/<int:id>', methods=['POST'])
def editar_unidade(id):
    u = Unidade.query.get_or_404(id)
    u.nome = request.form.get('nome'); u.cidade = request.form.get('cidade'); u.cnpj = limpar_input(request.form.get('cnpj'))
    u.contato = request.form.get('contato'); u.telefone = request.form.get('telefone'); u.email = request.form.get('email')
    db.session.commit(); flash('Atualizado!', 'success')
    return redirect(url_for('raizen'))

@app.route('/excluir_unidade/<int:id>', methods=['POST'])
def excluir_unidade(id):
    u = Unidade.query.get_or_404(id); db.session.delete(u); db.session.commit(); flash('Excluído!', 'success')
    return redirect(url_for('raizen'))

@app.route('/lancar_pedido', methods=['POST'])
def lancar_pedido():
    uid = request.form.get('unidade_id'); arq = request.files.get('arquivo')
    if uid and arq:
        path = os.path.join(PASTA_PDFS, arq.filename.replace(" ", "_"))
        arq.save(path)
        db.session.add(Pedido(arquivo=arq.filename.replace(" ", "_"), unidade_id=uid, observacao=request.form.get('observacao'), data_upload=datetime.now().date()))
        db.session.commit(); flash('Pedido lançado!', 'success')
    if request.form.get('origem') == 'detalhe': return redirect(url_for('detalhe_unidade', id=uid))
    return redirect(url_for('raizen'))

@app.route('/concluir_pedido/<int:id>')
def concluir_pedido(id):
    p = Pedido.query.get(id)
    if p: p.status = 'Concluído'; db.session.commit(); flash('Concluído!', 'success')
    return redirect(request.referrer or url_for('raizen'))

@app.route('/excluir_pedido/<int:id>', methods=['POST'])
def excluir_pedido(id):
    p = Pedido.query.get_or_404(id); uid = p.unidade_id; db.session.delete(p); db.session.commit(); flash('Excluído.', 'success')
    return redirect(url_for('detalhe_unidade', id=uid))

@app.route('/editar_pedido_obs/<int:id>', methods=['POST'])
def editar_pedido_obs(id):
    p = Pedido.query.get_or_404(id); p.observacao = request.form.get('observacao'); db.session.commit(); flash('Atualizado.', 'success')
    return redirect(url_for('detalhe_unidade', id=p.unidade_id))

@app.route('/adicionar_contato/<int:unidade_id>', methods=['POST'])
def adicionar_contato(unidade_id):
    nome = request.form.get('nome')
    if nome:
        db.session.add(Contato(nome=nome, cargo=request.form.get('cargo'), telefone=request.form.get('telefone'), email=request.form.get('email'), unidade_id=unidade_id))
        db.session.commit(); flash('Contato adicionado!', 'success')
    return redirect(url_for('detalhe_unidade', id=unidade_id))

@app.route('/editar_contato/<int:id>', methods=['POST'])
def editar_contato(id):
    c = Contato.query.get_or_404(id)
    c.nome = request.form.get('nome'); c.cargo = request.form.get('cargo'); c.telefone = request.form.get('telefone'); c.email = request.form.get('email')
    db.session.commit(); flash('Contato atualizado!', 'success')
    return redirect(url_for('detalhe_unidade', id=c.unidade_id))

@app.route('/excluir_contato/<int:id>', methods=['POST'])
def excluir_contato(id):
    c = Contato.query.get_or_404(id); uid = c.unidade_id; db.session.delete(c); db.session.commit(); flash('Contato removido.', 'success')
    return redirect(url_for('detalhe_unidade', id=uid))

# --- COBRANÇA ---
@app.route('/cobranca', methods=['GET', 'POST'])
def cobranca():
    if request.method == 'POST':
        arquivo = request.files.get('planilha')
        if arquivo:
            try:
                if arquivo.filename.endswith('.csv'): df = pd.read_csv(arquivo, encoding='utf-8', sep=',') 
                else: df = pd.read_excel(arquivo)
                atualizados = 0; novos = 0
                for index, row in df.iterrows():
                    cnpj_raw = str(row.get('CNPJ_CPF', '')); cnpj_limpo = re.sub(r'\D', '', cnpj_raw)
                    if not cnpj_limpo: continue 
                    cliente = Cliente.query.filter_by(cnpj=cnpj_limpo).first()
                    razao = str(row.get('RAZAO_SOCIAL', '')).strip()
                    valor = pd.to_numeric(row.get('TOTAL_PROPOSTAS', 0), errors='coerce')
                    if pd.isna(valor): valor = 0.0
                    email_aprov = str(row.get('EMAIL_APROVACAO', '')).strip()
                    if email_aprov == 'nan': email_aprov = ''
                    tel = str(row.get('CELULAR', row.get('TELEFONE', '')))
                    vendedor = str(row.get('VENDEDOR', ''))
                    if cliente:
                        cliente.valor_pendente = float(valor); cliente.data_atualizacao = datetime.utcnow()
                        if not cliente.emails_cobranca and email_aprov: cliente.emails_cobranca = email_aprov
                        if cliente.valor_pendente > 0:
                            if cliente.status_cobranca == 'Ok': cliente.status_cobranca = 'Pendente'
                        else: cliente.status_cobranca = 'Ok'
                        atualizados += 1
                    else:
                        db.session.add(Cliente(razao_social=razao, cnpj=cnpj_limpo, emails_cobranca=email_aprov, telefone=tel, vendedor=vendedor, valor_pendente=float(valor), status_cobranca='Pendente' if float(valor) > 0 else 'Ok'))
                        novos += 1
                db.session.commit(); flash(f'Processado! {novos} novos, {atualizados} atualizados.', 'success')
            except Exception as e: flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('cobranca'))
    q = request.args.get('q', ''); query = Cliente.query
    if q:
        s = f"%{q}%"; query = query.filter(Cliente.razao_social.like(s) | Cliente.cnpj.like(s))
    clientes = query.order_by(Cliente.valor_pendente.desc()).all()
    return render_template('clientes_lista.html', clientes=clientes, q=q)

@app.route('/cliente/<int:id>', methods=['GET', 'POST'])
def detalhe_cliente(id):
    c = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        c.emails_cobranca = request.form.get('emails_cobranca'); c.telefone = request.form.get('telefone')
        c.observacoes_internas = request.form.get('observacoes'); c.status_cobranca = request.form.get('status')
        db.session.commit(); flash('Salvo.', 'success')
        return redirect(url_for('detalhe_cliente', id=id))
    return render_template('detalhe_cliente.html', cliente=c)

with app.app_context(): db.create_all()
if __name__ == '__main__': app.run(debug=True)