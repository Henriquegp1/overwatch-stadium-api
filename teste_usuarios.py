import requests

# O endereço onde nosso servidor de usuários está rodando
BASE_URL = "http://127.0.0.1:8000/api/usuarios"

print("--- 1. TESTANDO CADASTRO ---")
dados_cadastro = {
    "email": "capitao_furia@teste.com",
    "senha": "senha_facil_123",
    "cargo": "capitao"
}

# Enviando o cadastro para a API
resp_cadastro = requests.post(f"{BASE_URL}/registrar", json=dados_cadastro)
print("Status Cadastro:", resp_cadastro.status_code)
print("Resposta:", resp_cadastro.json())


print("\n--- 2. TESTANDO LOGIN ---")
dados_login = {
    "email": "capitao_furia@teste.com",
    "senha": "senha_facil_123"
}

# Tentando fazer login com os mesmos dados
resp_login = requests.post(f"{BASE_URL}/login", json=dados_login)
print("Status Login:", resp_login.status_code)

if resp_login.status_code == 200:
    meu_token = resp_login.json().get("access_token")
    print("\n✅ LOGIN APROVADO! O seu Banco de Dados escondeu a senha e liberou este Token JWT:")
    print(f"\n{meu_token}\n")
    print("(A partir de agora, o capitão usa esse código gigante invisível para provar quem ele é, sem precisar mandar a senha de novo).")
else:
    print("Falha no login:", resp_login.json())