from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
import os
import re
import pandas as pd
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

def link_whatsapp(telefone):
    digits = re.sub(r'\D', '', telefone or '')
    if not digits:
        return ''
    if not digits.startswith('55'):
        digits = '55' + digits
    return f'https://wa.me/{digits}'

app.jinja_env.filters['cnpj'] = formatar_cnpj
app.jinja_env.filters['moeda'] = formatar_moeda
app.jinja_env.filters['whatsapp'] = link_whatsapp

CRITICO_DIAS = 15

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

    @property
    def numero(self):
        """Número do pedido: nome do PDF sem a extensão (ex: 361114.pdf -> 361114)."""
        return os.path.splitext(self.arquivo)[0]

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(20), unique=True)
    emails_cobranca = db.Column(db.Text)
    telefone = db.Column(db.String(50))
    vendedor = db.Column(db.String(100))
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)
    propostas = db.relationship('Proposta', backref='cliente', lazy=True, cascade="all, delete-orphan")

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

# --- ROTAS GERAIS ---

@app.route('/')
def dashboard():
    total_unidades = Unidade.query.count()
    total_pedidos = Pedido.query.count()
    
    pedidos_pendentes = Pedido.query.filter_by(status='Pendente').count()
    pedidos_cobrados = Pedido.query.filter_by(status='Cobrado').count()
    pedidos_concluidos = Pedido.query.filter_by(status='Concluído').count()
    
    ultimos_pedidos = Pedido.query.order_by(Pedido.data_upload.desc()).limit(5).all()

    clientes_ativos = [c for c in Cliente.query.options(joinedload(Cliente.propostas)).all() if c.valor_pendente > 0]
    clientes_ativos.sort(key=lambda c: c.valor_pendente, reverse=True)

    total_divida = sum(c.valor_pendente for c in clientes_ativos)
    qtd_devedores = len(clientes_ativos)
    maior_devedor = clientes_ativos[0] if clientes_ativos else None

    top_devedores = clientes_ativos[:5]
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

    clientes_por_cnpj = {c.cnpj: c for c in Cliente.query.options(joinedload(Cliente.propostas)).all()}
    for u in unidades:
        u.cliente_vinculado = clientes_por_cnpj.get(limpar_input(u.cnpj))

    # --- ORDENAÇÃO INTELIGENTE ---
    # 3 = Pedido pendente ou proposta crítica (+15 dias) -> Topo
    # 2 = Tem proposta pendente (sem estar crítica ainda)
    # 1 = Sem pendência ativa, mas tem pedido/proposta em negociação/cobrado
    # 0 = Sem nenhuma pendência
    def get_prioridade(u):
        tem_pedido_pendente = any(p.status == 'Pendente' for p in u.pedidos)
        tem_pedido_cobrado = any(p.status == 'Cobrado' for p in u.pedidos)
        cliente = u.cliente_vinculado
        tem_proposta_critica = bool(cliente) and cliente.dias_parado_maximo > CRITICO_DIAS
        tem_proposta_pendente = bool(cliente) and cliente.status_cobranca == 'Pendente'
        tem_proposta_negociando = bool(cliente) and cliente.status_cobranca == 'Negociando'

        if tem_pedido_pendente or tem_proposta_critica: return 3
        if tem_proposta_pendente: return 2
        if tem_pedido_cobrado or tem_proposta_negociando: return 1
        return 0

    # Ordena pela prioridade (maior primeiro) e depois pelo nome
    unidades = sorted(unidades, key=lambda u: (get_prioridade(u), u.nome), reverse=True)

    return render_template('raizen.html', unidades=unidades, q=q, critico_dias=CRITICO_DIAS)

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

    cnpj_limpo = limpar_input(u.cnpj)
    cliente = Cliente.query.options(joinedload(Cliente.propostas)).filter_by(cnpj=cnpj_limpo).first() if cnpj_limpo else None
    propostas = sorted(cliente.propostas, key=lambda p: p.dias_parado, reverse=True) if cliente else []

    return render_template('detalhe_unidade.html', unidade=u, pendentes=p1, cobrados=p2, concluidos=p3,
                           cliente=cliente, propostas=propostas, critico_dias=CRITICO_DIAS)

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

def parse_valor_brl(valor_str):
    if valor_str is None or (isinstance(valor_str, float) and pd.isna(valor_str)):
        return 0.0
    limpo = str(valor_str).replace('R$', '').strip().replace('.', '').replace(',', '.')
    try:
        return float(limpo)
    except (ValueError, TypeError):
        return 0.0

def parse_data_proposta(data_str):
    if not data_str or (isinstance(data_str, float) and pd.isna(data_str)):
        return None
    try:
        return datetime.strptime(str(data_str).strip(), '%d/%m/%Y %H:%M')
    except (ValueError, TypeError):
        return None

def campo(row, nome):
    valor = row.get(nome, '')
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ''
    return str(valor).strip()

@app.route('/cobranca', methods=['GET', 'POST'])
def cobranca():
    if request.method == 'POST':
        arquivo = request.files.get('planilha')
        if arquivo:
            try:
                if arquivo.filename.endswith('.csv'):
                    df = pd.read_csv(arquivo, encoding='utf-8-sig', sep=None, engine='python', dtype=str)
                else:
                    df = pd.read_excel(arquivo, dtype=str)
                df.columns = [str(c).strip() for c in df.columns]

                propostas_novas = 0
                propostas_atualizadas = 0
                clientes_novos = 0
                numeros_no_import = set()

                for _, row in df.iterrows():
                    cnpj_raw = campo(row, 'Cnpj/Cpf')
                    cnpj_limpo = re.sub(r'\D', '', cnpj_raw)
                    if not cnpj_limpo:
                        continue

                    numero_proposta = campo(row, 'Nº Proposta')
                    if not numero_proposta:
                        continue
                    numeros_no_import.add(numero_proposta)

                    razao = campo(row, 'Razão Social')
                    valor = parse_valor_brl(row.get('Total', 0))
                    data_criacao = parse_data_proposta(row.get('Data Criação'))
                    vendedor = campo(row, 'Vendedor')
                    contato = campo(row, 'Contato')
                    celular = campo(row, 'Celular')
                    telefone = campo(row, 'Telefone')
                    email_solicit = campo(row, 'Email Solicit.')
                    email_aprov = campo(row, 'Email Aprov.')
                    email_nf = campo(row, 'Email NF')

                    cliente = Cliente.query.filter_by(cnpj=cnpj_limpo).first()
                    if not cliente:
                        cliente = Cliente(razao_social=razao, cnpj=cnpj_limpo, emails_cobranca=email_aprov,
                                           telefone=celular or telefone, vendedor=vendedor)
                        db.session.add(cliente)
                        db.session.flush()
                        clientes_novos += 1

                    proposta = Proposta.query.filter_by(numero_proposta=numero_proposta).first()
                    if proposta:
                        proposta.valor = valor
                        proposta.data_criacao_proposta = data_criacao
                        proposta.contato = contato
                        proposta.celular = celular
                        proposta.telefone = telefone
                        proposta.email_solicit = email_solicit
                        proposta.email_aprov = email_aprov
                        proposta.email_nf = email_nf
                        proposta.vendedor = vendedor
                        propostas_atualizadas += 1
                    else:
                        db.session.add(Proposta(numero_proposta=numero_proposta, valor=valor,
                                                 data_criacao_proposta=data_criacao, status_cobranca='Pendente',
                                                 contato=contato, celular=celular, telefone=telefone,
                                                 email_solicit=email_solicit, email_aprov=email_aprov,
                                                 email_nf=email_nf, vendedor=vendedor, cliente_id=cliente.id))
                        propostas_novas += 1

                    cliente.data_atualizacao = datetime.utcnow()

                # Remove propostas que não vieram mais nesta importação
                propostas_removidas = Proposta.query.filter(~Proposta.numero_proposta.in_(numeros_no_import)).delete(synchronize_session=False)

                db.session.commit()

                flash(f'Processado! {clientes_novos} clientes novos, {propostas_novas} propostas novas, '
                      f'{propostas_atualizadas} atualizadas, {propostas_removidas} removidas.', 'success')
            except Exception as e:
                flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('cobranca'))

    q = request.args.get('q', '')
    filtro = request.args.get('filtro', 'todos')
    ordenar_valor = request.args.get('ordenar') == 'valor'

    todos_clientes = Cliente.query.options(joinedload(Cliente.propostas)).all()
    total_pendente = sum(c.valor_pendente for c in todos_clientes)
    total_negociando = sum(c.valor_negociando for c in todos_clientes)
    qtd_pendentes = sum(1 for c in todos_clientes if c.status_cobranca == 'Pendente')
    qtd_negociando = sum(1 for c in todos_clientes if c.status_cobranca == 'Negociando')
    qtd_criticos = sum(1 for c in todos_clientes if c.dias_parado_maximo > CRITICO_DIAS)

    clientes = todos_clientes
    if q:
        s = q.lower()
        clientes = [c for c in clientes if s in (c.razao_social or '').lower() or s in (c.cnpj or '')]

    if filtro == 'pendentes':
        clientes = [c for c in clientes if c.status_cobranca == 'Pendente']
    elif filtro == 'negociando':
        clientes = [c for c in clientes if c.status_cobranca == 'Negociando']
    elif filtro == 'criticos':
        clientes = [c for c in clientes if c.dias_parado_maximo > CRITICO_DIAS]
    elif filtro == 'ok':
        clientes = [c for c in clientes if c.status_cobranca == 'Ok']

    prioridade = {'Pendente': 0, 'Negociando': 1, 'Ok': 2}
    if ordenar_valor:
        clientes.sort(key=lambda c: (prioridade.get(c.status_cobranca, 1), -c.valor_pendente))
    else:
        clientes.sort(key=lambda c: (prioridade.get(c.status_cobranca, 1), -c.dias_parado_maximo, -c.valor_pendente))

    return render_template('clientes_lista.html', clientes=clientes, q=q, filtro=filtro, ordenar_valor=ordenar_valor,
                           total_pendente=total_pendente, total_negociando=total_negociando,
                           qtd_pendentes=qtd_pendentes, qtd_negociando=qtd_negociando,
                           qtd_criticos=qtd_criticos, critico_dias=CRITICO_DIAS)

@app.route('/proposta/<int:id>/status/<status>')
def marcar_status_proposta(id, status):
    p = Proposta.query.get(id)
    if p:
        p.status_cobranca = status
        db.session.commit()
        flash(f'Proposta #{p.numero_proposta}: {status}.', 'info')
    return redirect(request.referrer or url_for('cobranca'))

@app.route('/cliente/<int:id>/propostas/status/<status>')
def marcar_status_propostas_lote(id, status):
    cliente = Cliente.query.get_or_404(id)
    atualizadas = 0
    for p in cliente.propostas:
        if p.status_cobranca == 'Pendente':
            p.status_cobranca = status
            atualizadas += 1
    db.session.commit()
    flash(f'{atualizadas} proposta(s) marcadas como {status}.', 'info')
    return redirect(request.referrer or url_for('detalhe_cliente', id=id))

@app.route('/cliente/<int:id>')
def detalhe_cliente(id):
    c = Cliente.query.options(joinedload(Cliente.propostas)).get_or_404(id)
    return render_template('detalhe_cliente.html', cliente=c, critico_dias=CRITICO_DIAS)

with app.app_context(): db.create_all()
if __name__ == '__main__': app.run(debug=True)