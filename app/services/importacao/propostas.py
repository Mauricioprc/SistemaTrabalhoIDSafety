"""Importação de Propostas — comportamento idêntico ao antigo app.py,
apenas movido para a camada de serviço. Mantido fora da interface comum de
ImportadorBase porque seu fluxo (planilha inteira substitui o conjunto de
propostas ativas, com remoção do que não veio mais) é particular e já
existia em produção antes da Fase 1 — não deve mudar de comportamento."""
import io
from datetime import datetime

import pandas as pd

from app.extensions import db
from app.models import Cliente, Proposta
from app.utils.formatters import limpar_cnpj


def _parse_valor_brl(valor_str):
    if valor_str is None or (isinstance(valor_str, float) and pd.isna(valor_str)):
        return 0.0
    limpo = str(valor_str).replace('R$', '').strip().replace('.', '').replace(',', '.')
    try:
        return float(limpo)
    except (ValueError, TypeError):
        return 0.0


def _parse_data_proposta(data_str):
    if not data_str or (isinstance(data_str, float) and pd.isna(data_str)):
        return None
    try:
        return datetime.strptime(str(data_str).strip(), '%d/%m/%Y %H:%M')
    except (ValueError, TypeError):
        return None


def _campo(row, nome):
    valor = row.get(nome, '')
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ''
    return str(valor).strip()


def importar_propostas(arquivo):
    """Processa a planilha de propostas. Retorna dict com as contagens do
    resultado (clientes_novos, propostas_novas, propostas_atualizadas,
    propostas_removidas), igual à mensagem de flash original."""
    # Lê o conteúdo para um BytesIO puro antes de passar pro pandas: alguns
    # objetos file-like (ex: werkzeug.FileStorage, o que o Flask entrega em
    # request.files) fazem o sniffer de delimitador do pandas (sep=None,
    # engine='python') quebrar com "cannot use a string pattern on a
    # bytes-like object" — bug de interação entre o tipo do stream e o
    # csv.Sniffer, não do conteúdo em si.
    conteudo = io.BytesIO(arquivo.read())
    if arquivo.filename.endswith('.csv'):
        df = pd.read_csv(conteudo, encoding='utf-8-sig', sep=None, engine='python', dtype=str)
    else:
        df = pd.read_excel(conteudo, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    propostas_novas = 0
    propostas_atualizadas = 0
    clientes_novos = 0
    numeros_no_import = set()

    for _, row in df.iterrows():
        cnpj_raw = _campo(row, 'Cnpj/Cpf')
        cnpj_limpo = limpar_cnpj(cnpj_raw)
        if not cnpj_limpo:
            continue

        numero_proposta = _campo(row, 'Nº Proposta')
        if not numero_proposta:
            continue
        numeros_no_import.add(numero_proposta)

        razao = _campo(row, 'Razão Social')
        valor = _parse_valor_brl(row.get('Total', 0))
        data_criacao = _parse_data_proposta(row.get('Data Criação'))
        vendedor = _campo(row, 'Vendedor')
        contato = _campo(row, 'Contato')
        celular = _campo(row, 'Celular')
        telefone = _campo(row, 'Telefone')
        email_solicit = _campo(row, 'Email Solicit.')
        email_aprov = _campo(row, 'Email Aprov.')
        email_nf = _campo(row, 'Email NF')

        cliente = Cliente.query.filter_by(cnpj=cnpj_limpo).first()
        if not cliente:
            cliente = Cliente(razao_social=razao, cnpj=cnpj_limpo, emails_cobranca=email_aprov,
                               telefone=celular or telefone, vendedor=vendedor,
                               data_cadastro=datetime.utcnow())
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

    propostas_removidas = Proposta.query.filter(
        ~Proposta.numero_proposta.in_(numeros_no_import)).delete(synchronize_session=False)

    db.session.commit()

    return {
        'clientes_novos': clientes_novos,
        'propostas_novas': propostas_novas,
        'propostas_atualizadas': propostas_atualizadas,
        'propostas_removidas': propostas_removidas,
    }
