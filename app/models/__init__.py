from app.models.cliente import Cliente, Contato
from app.models.proposta import Proposta, Unidade
from app.models.pedido import Pedido
from app.models.tarefa import Tarefa
from app.models.indicadores import IndicadorRetencao, NotaNPS, ClasseABC, RazaoSocialAlias

__all__ = [
    'Cliente', 'Contato', 'Proposta', 'Unidade', 'Pedido', 'Tarefa',
    'IndicadorRetencao', 'NotaNPS', 'ClasseABC', 'RazaoSocialAlias',
]
