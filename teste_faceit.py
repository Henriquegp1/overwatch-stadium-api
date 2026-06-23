import requests
from database.connection import SessionLocal
from database.models import Partida

# --- 1. PREPARANDO O TERRENO ---
# Vamos abrir o banco de dados e inserir uma partida agendada
db = SessionLocal()

# Verifica se a partida já existe para não dar erro se rodarmos o teste 2 vezes
partida_teste = db.query(Partida).filter(Partida.faceit_match_id == "jogo-teste-001").first()
if not partida_teste:
    nova_partida = Partida(faceit_match_id="jogo-teste-001", status="agendada")
    db.add(nova_partida)
    db.commit()
    print("[1] Partida agendada no banco de dados com sucesso!")
else:
    print("[1] Partida já estava no banco.")

db.close()

# --- 2. O ATAQUE (SIMULANDO A FACEIT) ---
print("[2] Simulando envio do Webhook da FACEIT...")

url_do_seu_sistema = "http://127.0.0.1:8000/api/webhooks/faceit"

# O "Crachá" de segurança que configuramos no .env
headers = {
    "Authorization": "Bearer minha_senha_secreta_da_faceit_123"
}

# O JSON idêntico ao que a FACEIT manda quando um jogo termina em 3x0
payload_falso = {
    "event": "match_status_finished",
    "match_id": "jogo-teste-001",
    "payload": {
        "id": "jogo-teste-001",
        "teams": {
            "faction1": {"id": "t1", "name": "Time A", "score": 3},
            "faction2": {"id": "t2", "name": "Time B", "score": 0}
        },
        "results": {
            "winner": "faction1"
        }
    }
}

# Disparando a requisição contra o seu próprio servidor
resposta = requests.post(url_do_seu_sistema, json=payload_falso, headers=headers)

print("\n--- RESULTADO DO SEU SISTEMA ---")
print("Status Code:", resposta.status_code)
print("Resposta JSON:", resposta.json())