from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os

# Importa a conexão do banco e a tabela de Partidas
from database.connection import get_db
from database.models import Partida

# Cria o roteador para organizar as URLs
router = APIRouter()

# --- MODELOS DE VALIDAÇÃO (O "Escudo" do JSON) ---
class Faction(BaseModel):
    id: str
    name: str
    score: int

class Teams(BaseModel):
    faction1: Faction
    faction2: Faction

class Results(BaseModel):
    winner: str

class MatchPayload(BaseModel):
    id: str
    teams: Teams
    results: Results

class FaceitWebhook(BaseModel):
    event: str
    match_id: str
    payload: MatchPayload

# --- A ROTA PRINCIPAL ---
@router.post("/faceit")
def receber_webhook_faceit(
    webhook_data: FaceitWebhook, 
    authorization: str = Header(None),
    db: Session = Depends(get_db) # Abre a conexão com o banco de forma segura
):
    # 1. Checa a senha da FACEIT
    senha_correta = f"Bearer {os.getenv('FACEIT_SECRET_TOKEN')}"
    if authorization != senha_correta:
        raise HTTPException(status_code=401, detail="Invasão detectada. Senha incorreta.")

    # 2. Ignora se não for o fim da partida
    if webhook_data.event != "match_status_finished":
        return {"status": "ignorado"}

    # 3. Puxa os placares
    match_id = webhook_data.match_id
    score_f1 = webhook_data.payload.teams.faction1.score
    score_f2 = webhook_data.payload.teams.faction2.score

    # 4. Procura a partida no Banco de Dados
    partida_no_banco = db.query(Partida).filter(Partida.faceit_match_id == match_id).first()
    
    # Se a partida não existir no nosso banco, a gente avisa e para por aqui
    if not partida_no_banco:
        return {"status": "erro", "detalhe": "Partida não encontrada no banco de dados."}

    # 5. Aplica a Regra do Overwatch Stadium (10.000 pontos)
    if (score_f1 == 3 and score_f2 == 0) or (score_f1 == 0 and score_f2 == 3):
        partida_no_banco.status = "aguardando_validacao_stadium"
        mensagem = "Placar 3x0. Sistema travou a partida aguardando print do capitão."
    else:
        partida_no_banco.status = "concluida"
        mensagem = "Partida normal. Status atualizado para concluída."

    # Salva as alterações no banco de dados com segurança
    db.commit()

    return {"status": "sucesso", "acao": mensagem}