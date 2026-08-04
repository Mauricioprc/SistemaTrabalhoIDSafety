import os

from flask import Flask

from app.extensions import db, migrate
from app.utils.formatters import formatar_cnpj, formatar_moeda, link_whatsapp


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
    app.secret_key = 'chave_secreta_raizen_sistema_id'

    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app.config['BASEDIR'] = basedir
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'raizen_gestao.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    pasta_pdfs = os.path.join(basedir, 'static', 'pedidos_pdfs')
    os.makedirs(pasta_pdfs, exist_ok=True)
    app.config['PASTA_PDFS'] = pasta_pdfs

    db.init_app(app)
    migrate.init_app(app, db)

    app.jinja_env.filters['cnpj'] = formatar_cnpj
    app.jinja_env.filters['moeda'] = formatar_moeda
    app.jinja_env.filters['whatsapp'] = link_whatsapp

    from app import models  # noqa: F401 garante que os modelos são registrados no db antes das migrations

    from app.routes import register_blueprints
    register_blueprints(app)

    return app
