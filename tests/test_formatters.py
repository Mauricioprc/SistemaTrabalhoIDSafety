"""app/utils/formatters.py — limpar_cnpj() (usada em toda importação que
grava Cliente.cnpj) e formatar_cnpj() (só exibição)."""
import logging

from app.utils.formatters import formatar_cnpj, limpar_cnpj


def test_limpar_cnpj_remove_pontuacao():
    assert limpar_cnpj('12.345.678/0001-90') == '12345678000190'


def test_limpar_cnpj_ja_limpo_fica_igual():
    assert limpar_cnpj('12345678000190') == '12345678000190'


def test_limpar_cnpj_vazio_retorna_vazio():
    assert limpar_cnpj('') == ''
    assert limpar_cnpj(None) == ''


def test_limpar_cnpj_com_menos_de_14_digitos_nao_descarta_so_avisa(caplog):
    with caplog.at_level(logging.WARNING):
        resultado = limpar_cnpj('111.437.278-19')  # CPF, 11 dígitos
    assert resultado == '11143727819'  # dado preservado, não descartado
    assert any('11 dígitos' in r.message or '11' in r.message for r in caplog.records)


def test_formatar_cnpj_so_pontua_com_14_digitos():
    assert formatar_cnpj('12345678000190') == '12.345.678/0001-90'
    assert formatar_cnpj('11143727819') == '11143727819'  # não é CNPJ, fica cru
