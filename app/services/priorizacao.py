"""Score de priorização de clientes.

Regra de negócio explícita e auditável (não é machine learning). Cada peso é
documentado abaixo; recalculado a cada importação de qualquer fonte, via
`recalcular_todos()`. `score_prioridade` e `motivo_prioridade` em Cliente são
derivados: nunca a fonte de verdade, sempre resultado deste cálculo.
"""
from app.extensions import db
from app.models import Cliente

# Pesos (quanto maior, mais urgente). Ajustáveis, mas sempre comentados.
PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE = 100  # sinal mais forte: cliente valioso, prestes a cair, com proposta parada
PESO_ALERTA_NPS_BAIXO_CLASSE_A = 60             # cliente Classe A insatisfeito, mesmo sem previsão formal de queda
PESO_ATRASO_FREQUENCIA_COMPRA = 40              # sinal antecipado de queda, antes da previsão formal do indicador
PESO_PROPOSTA_CRITICA = 20                      # proposta pendente já além do limite de dias considerado crítico

NPS_NOTA_BAIXA = 6
CRITICO_DIAS = 15

# Dias esperados sem pedido para cada frequência de compra antes de soar o alerta
# antecipado (ex.: "Mensal" tolera até 45 dias sem novo pedido).
DIAS_ESPERADOS_POR_FREQUENCIA = {
    'Mensal': 45,
    'Trimestral': 100,
    'Semestral': 200,
    'Anual': 400,
}


def calcular_score(cliente: Cliente):
    score = 0
    motivos = []

    retencao = cliente.indicador_retencao
    classe_atual = cliente.classe_abc_atual
    classe = classe_atual.classe if classe_atual else None
    nota_recente = cliente.nota_nps_mais_recente

    tem_proposta_pendente = cliente.qtd_pendentes > 0

    if retencao and retencao.ira_cair and classe in ('A', 'B') and tem_proposta_pendente:
        score += PESO_RISCO_QUEDA_CLASSE_AB_COM_PENDENTE
        motivos.append(f'Classe {classe} + risco de queda + proposta pendente')

    if nota_recente and nota_recente.nota <= NPS_NOTA_BAIXA and classe == 'A':
        score += PESO_ALERTA_NPS_BAIXO_CLASSE_A
        motivos.append(f'Alerta: nota NPS {nota_recente.nota} em cliente Classe A')

    if retencao and retencao.frequencia_compra in DIAS_ESPERADOS_POR_FREQUENCIA:
        esperado = DIAS_ESPERADOS_POR_FREQUENCIA[retencao.frequencia_compra]
        dias = retencao.dias_desde_ultimo_pedido or 0
        if dias > esperado:
            score += PESO_ATRASO_FREQUENCIA_COMPRA
            motivos.append(
                f'Sem pedido há {dias} dias (frequência {retencao.frequencia_compra}, '
                f'esperado até {esperado} dias)')

    dias_parado = cliente.dias_parado_maximo
    if dias_parado > CRITICO_DIAS:
        score += PESO_PROPOSTA_CRITICA
        motivos.append(f'Proposta pendente parada há {dias_parado} dias')

    motivo = '; '.join(motivos) if motivos else 'Sem sinais de risco identificados'
    return score, motivo


def recalcular_todos():
    """Recalcula score_prioridade/motivo_prioridade de todos os clientes.
    Chamado ao final de cada importação (qualquer fonte)."""
    for cliente in Cliente.query.all():
        score, motivo = calcular_score(cliente)
        cliente.score_prioridade = score
        cliente.motivo_prioridade = motivo
    db.session.commit()
