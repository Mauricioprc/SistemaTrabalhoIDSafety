import re
import sys
import os

# Tenta importar o app. Se der erro de biblioteca, avisa o usuário.
try:
    from app import app, db, Unidade
except ImportError as e:
    print("\nERRO CRÍTICO DE IMPORTAÇÃO!")
    print(f"Detalhe: {e}")
    print("DICA: Provavelmente falta instalar o pandas. Rode no terminal:")
    print("pip install pandas openpyxl")
    sys.exit(1)

def limpar(texto):
    """Remove tudo que não for número"""
    return re.sub(r'\D', '', str(texto))

# Dados das unidades (Raízen)
dados_unidades = [
    {"nome": "Raízen Centro-Sul S.A.", "cnpj": "15.527.906/0007-21", "cidade": "Rio Brilhante/MS"},
    {"nome": "RAIZEN CENTRO-SUL S.A", "cnpj": "15.527.906/0035-85", "cidade": "Rio Brilhante/MS"},
    {"nome": "Raízen Biomassa S.A.", "cnpj": "12.489.586/0002-60", "cidade": "Jaú/SP"},
    {"nome": "RAIZEN-GEO BIOGAS COSTA PINTO LTDA", "cnpj": "45.281.972/0001-30", "cidade": "Piracicaba/SP"},
    {"nome": "RAIZEN S.A BIOENERGIA", "cnpj": "07.362.852/0005-00", "cidade": "Elias Fausto/SP"},
    {"nome": "Raízen Centro-Sul Paulista S.A.", "cnpj": "49.213.747/0129-80", "cidade": "Colômbia/SP"},
    {"nome": "Raízen Centro-Sul Paulista S.A.", "cnpj": "49.213.747/0001-17", "cidade": "Morro Agudo/SP"},
    {"nome": "Raízen Centro-Sul Paulista S.A.", "cnpj": "49.213.747/0118-28", "cidade": "Sertãozinho/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0072-61", "cidade": "Jaú/SP"},
    {"nome": "Raízen Centro-Sul S.A.", "cnpj": "15.527.906/0029-37", "cidade": "Lagoa da Prata/MG"},
    {"nome": "Raízen Centro-Sul Paulista S.A.", "cnpj": "49.213.747/0115-85", "cidade": "Morro Agudo/SP"},
    {"nome": "Inativação CNPJ Raízen Centro-Sul S.A", "cnpj": "15.527.906/0036-66", "cidade": "Leme/SP"},
    {"nome": "Raizen Caarapó Açucar e Alcool Ltda", "cnpj": "09.538.989/0004-09", "cidade": "Paraguaçu Paulista/SP"},
    {"nome": "Raizen Caarapó Açucar e Alcool Ltda", "cnpj": "09.538.989/0006-70", "cidade": "Maracaí/SP"},
    {"nome": "Raizen Caarapó Açucar e Alcool Ltda", "cnpj": "09.538.989/0007-51", "cidade": "Tarumã/SP"},
    {"nome": "RAIZEN ENERGIA S.A.", "cnpj": "08.070.508/0167-67", "cidade": "Jataí/GO"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0164-14", "cidade": "Araraquara/SP"},
    {"nome": "RAIZEN BIOGAS LTDA", "cnpj": "25.201.024/0001-30", "cidade": "Guariba/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0122-65", "cidade": "Rafard/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0096-39", "cidade": "Elias Fausto/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0094-77", "cidade": "Rio das Pedras/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0121-84", "cidade": "Piracicaba/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0158-76", "cidade": "Brotas/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0157-95", "cidade": "Bocaina/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0095-58", "cidade": "Jaú/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0003-30", "cidade": "Barra Bonita/SP"},
    {"nome": "RAIZEN CAARAPO ACUCAR E ALCOOL LTDA", "cnpj": "09.538.989/0001-66", "cidade": "Caarapó/MS"},
    {"nome": "Raizen Energia S.A.", "cnpj": "08.070.508/0069-66", "cidade": "Ipaussu/SP"},
    {"nome": "Raizen Energia S.A.", "cnpj": "08.070.508/0124-27", "cidade": "Igarapava/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0125-08", "cidade": "Ibaté/SP"},
    {"nome": "Raizen Energia S.A.", "cnpj": "08.070.508/0065-32", "cidade": "Guariba/SP"},
    {"nome": "Raizen Energia S.A.", "cnpj": "08.070.508/0066-13", "cidade": "Araçatuba/SP"},
    {"nome": "Raizen Energia S.A.", "cnpj": "08.070.508/0068-85", "cidade": "Andradina/SP"},
    {"nome": "Raizen Energia S.A.", "cnpj": "08.070.508/0067-02", "cidade": "Valparaíso/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0097-10", "cidade": "Mirandópolis/SP"},
    {"nome": "RAIZEN ENERGIA S.A", "cnpj": "08.070.508/0083-14", "cidade": "Bento de Abreu/SP"},
    {"nome": "Raízen Energia S.A.", "cnpj": "08.070.508/0093-96", "cidade": "Piracicaba/SP"},
    {"nome": "RZ AGRICOLA CAARAPO LTDA", "cnpj": "09.538.958/0001-05", "cidade": "Caarapó/MS"}
]

print("-" * 40)
print(f"Iniciando processo para {len(dados_unidades)} unidades...")

with app.app_context():
    # 1. Garante que o banco e as tabelas existem
    db.create_all()
    print("Banco de dados verificado/criado com sucesso.")
    
    contador = 0
    ignorados = 0
    
    for item in dados_unidades:
        cnpj_limpo = limpar(item['cnpj'])
        
        # Verifica se já existe para não duplicar
        existe = Unidade.query.filter_by(cnpj=cnpj_limpo).first()
        
        if not existe:
            nova = Unidade(
                nome=item['nome'],
                cnpj=cnpj_limpo,
                cidade=item['cidade'],
                contato="",
                telefone="",
                email=""
            )
            db.session.add(nova)
            contador += 1
            print(f"[OK] Cadastrado: {item['nome']}")
        else:
            ignorados += 1
            # print(f"[PULOU] Já existe: {item['nome']}") # Descomente se quiser ver
            
    db.session.commit()
    print("-" * 40)
    print(f"CONCLUÍDO!")
    print(f"Novos cadastros: {contador}")
    print(f"Já existiam: {ignorados}")
    print("Agora você pode rodar 'python app.py'")