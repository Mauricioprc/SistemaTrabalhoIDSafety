# Sistema de Trabalho — ID Safety

Painel interno de apoio a vendas/cobrança (Flask + SQLAlchemy + SQLite).

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | Sim (fora de dev) | Chave de sessão do Flask. Gere com `python -c "import secrets; print(secrets.token_hex(32))"`. Em dev (`FLASK_DEBUG=1`) é opcional — cai para uma chave aleatória gerada a cada restart. |
| `FLASK_DEBUG` | Não (default `False`) | `1`/`true` liga o modo debug (reload automático, traceback interativo). **Nunca `1` em produção** — expõe execução de código arbitrário via o debugger do Werkzeug. |
| `AUTH_USER` / `AUTH_PASSWORD` | Sim | Credencial única de HTTP Basic Auth que protege todas as rotas. |
| `PORT` | Não (default `5000`) | Porta do servidor de desenvolvimento (`run.py`). Ignorada em produção via WSGI. |

## Rodando em desenvolvimento (Windows/PowerShell)

```powershell
$env:FLASK_DEBUG = "1"
$env:AUTH_USER = "admin"
$env:AUTH_PASSWORD = "troque-isso"
py run.py
```

`SECRET_KEY` pode ficar de fora em dev — o app gera uma automaticamente e avisa no console. Se quiser fixar (pra sessões sobreviverem a um reload), defina também `$env:SECRET_KEY`.

## Rodando em desenvolvimento (bash/Linux/macOS)

```bash
export FLASK_DEBUG=1
export AUTH_USER=admin
export AUTH_PASSWORD=troque-isso
python run.py
```

## Rodando em produção

Nunca defina `FLASK_DEBUG`. Defina `SECRET_KEY`, `AUTH_USER` e `AUTH_PASSWORD` de verdade. Sirva com um WSGI de produção — não use `run.py`/`app.run()` diretamente (é o servidor de desenvolvimento do Werkzeug, não é feito pra carga real).

### PythonAnywhere

1. No painel **Web**, configure o WSGI file gerado pelo PythonAnywhere pra importar o app deste projeto:

   ```python
   import sys
   path = '/home/SEU_USUARIO/SistemaTrabalhoIDSafety'
   if path not in sys.path:
       sys.path.insert(0, path)

   from app import create_app
   application = create_app()
   ```

2. Na aba **Web → Environment variables** (ou via um `.env` carregado antes do import, se sua conta não tiver essa aba), defina `SECRET_KEY`, `AUTH_USER`, `AUTH_PASSWORD`. **Não defina `FLASK_DEBUG`.**
3. Recarregue o app (botão **Reload**) depois de qualquer mudança de variável de ambiente ou de código.

### WSGI genérico (gunicorn, uWSGI, etc.)

O padrão de application factory já expõe o que esses servidores esperam:

```bash
export SECRET_KEY=... AUTH_USER=... AUTH_PASSWORD=...
gunicorn "app:create_app()"
```

## Testes

```bash
pytest
```

Roda sempre contra um banco SQLite em memória — nunca contra `raizen_gestao.db`.

## Migrations

```bash
export FLASK_APP=run.py
flask db upgrade      # aplica migrations pendentes
flask db migrate -m "descrição"   # gera uma nova migration a partir de mudanças nos models
```
