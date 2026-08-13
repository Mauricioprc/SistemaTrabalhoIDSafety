import os
import secrets
import warnings

from flask import Flask, flash, redirect, request, session, url_for

from app.extensions import db, migrate
from app.utils.formatters import formatar_cnpj, formatar_moeda, link_whatsapp


def _resolver_credenciais_auth():
    """AUTH_USER/AUTH_PASSWORD são obrigatórias sempre — não tem fallback de
    dev aqui como em SECRET_KEY, porque autenticação sem credencial não é
    autenticação nenhuma. Sem elas, o app nem sobe."""
    usuario = os.environ.get('AUTH_USER')
    senha = os.environ.get('AUTH_PASSWORD')
    if not usuario or not senha:
        raise RuntimeError(
            'AUTH_USER e AUTH_PASSWORD precisam estar definidas nas variáveis de '
            'ambiente — o sistema lida com dados de clientes e não pode ficar '
            'aberto sem autenticação.')
    return usuario, senha


def _resolver_secret_key():
    """SECRET_KEY vem de variável de ambiente. Em dev (FLASK_DEBUG=1) cai
    para uma chave aleatória gerada na hora — troca a cada restart, então
    sessões/flash não sobrevivem a um reload, mas isso não trava o dev local
    sem configurar nada. Em produção (FLASK_DEBUG não setado/false) a
    ausência de SECRET_KEY é um erro explícito: nunca sobe com uma chave
    hardcoded ou adivinhada."""
    secret_key = os.environ.get('SECRET_KEY')
    if secret_key:
        return secret_key

    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    if debug:
        warnings.warn(
            'SECRET_KEY não definida — usando chave aleatória temporária (só '
            'para dev). Defina a variável de ambiente SECRET_KEY antes de ir '
            'para produção.', RuntimeWarning)
        return secrets.token_hex(32)

    raise RuntimeError(
        'SECRET_KEY não definida. Configure a variável de ambiente SECRET_KEY '
        '(ex: python -c "import secrets; print(secrets.token_hex(32))") antes '
        'de rodar fora de FLASK_DEBUG=1.')


def create_app(config_overrides=None):
    """`config_overrides` é aplicado ANTES de `db.init_app(app)` — o
    Flask-SQLAlchemy lê SQLALCHEMY_DATABASE_URI já em init_app, então
    sobrescrever app.config depois de chamar create_app() não isola nada
    (foi exatamente isso que causou um data loss no banco de dev: os testes
    trocavam a URI depois do fato e acabavam batendo no arquivo real). Testes
    devem sempre passar config_overrides={'SQLALCHEMY_DATABASE_URI': ...}
    aqui, nunca mutar app.config após o retorno desta função."""
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
    app.secret_key = _resolver_secret_key()
    _resolver_credenciais_auth()  # só valida na subida que AUTH_USER/AUTH_PASSWORD existem

    ENDPOINTS_PUBLICOS = {'auth.login', 'static'}

    @app.before_request
    def exigir_autenticacao():
        if request.endpoint in ENDPOINTS_PUBLICOS:
            return None
        if not session.get('autenticado'):
            return redirect(url_for('auth.login', next=request.path))

    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app.config['BASEDIR'] = basedir
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'raizen_gestao.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    pasta_pdfs = os.path.join(basedir, 'static', 'pedidos_pdfs')
    os.makedirs(pasta_pdfs, exist_ok=True)
    app.config['PASTA_PDFS'] = pasta_pdfs

    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB — suficiente pra qualquer planilha

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    migrate.init_app(app, db)

    app.jinja_env.filters['cnpj'] = formatar_cnpj
    app.jinja_env.filters['moeda'] = formatar_moeda
    app.jinja_env.filters['whatsapp'] = link_whatsapp

    from app import models  # noqa: F401 garante que os modelos são registrados no db antes das migrations

    from app.routes import register_blueprints
    register_blueprints(app)

    @app.errorhandler(413)
    def arquivo_grande_demais(_erro):
        limite_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        flash(f'Arquivo grande demais (limite de {limite_mb}MB). Divida a planilha em partes menores '
              'e importe cada uma separadamente.', 'danger')
        return redirect(request.referrer or url_for('importacao.importacao'))

    return app
