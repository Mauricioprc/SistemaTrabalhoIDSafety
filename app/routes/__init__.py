def register_blueprints(app):
    from app.routes.auth import bp as auth_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.cobranca import bp as cobranca_bp
    from app.routes.clientes import bp as clientes_bp
    from app.routes.importacao import bp as importacao_bp
    from app.routes.tarefas import bp as tarefas_bp
    from app.routes.raizen import bp as raizen_bp
    from app.routes.radar import bp as radar_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(cobranca_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(importacao_bp)
    app.register_blueprint(tarefas_bp)
    app.register_blueprint(raizen_bp)
    app.register_blueprint(radar_bp)
