# -*- coding: utf-8 -*-
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import os

from database.connection import get_db
from database.models import Partida, Equipe

router = APIRouter()


# --- MODELOS DE VALIDAÇÃO DO JSON DA FACEIT ---
class Faction(BaseModel):
    id: str
    name: str
    score: int

class Teams(BaseModel):
    faction1: Faction
    faction2: Faction

class Results(BaseModel):
    winner: str  # 'faction1' ou 'faction2'

class MatchPayload(BaseModel):
    id: str
    teams: Teams
    results: Results

class FaceitWebhook(BaseModel):
    event: str
    match_id: str
    payload: MatchPayload


@router.post("/faceit")
def receber_webhook_faceit(
    webhook_data: FaceitWebhook,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    # 1. Valida a assinatura da FACEIT
    senha_correta = f"Bearer {os.getenv('FACEIT_SECRET_TOKEN')}"
    if authorization != senha_correta:
        raise HTTPException(status_code=401, detail="Token inválido.")

    # 2. Ignora eventos que não sejam fim de partida
    if webhook_data.event != "match_status_finished":
        return {"status": "ignorado", "evento": webhook_data.event}

    match_id = webhook_data.match_id
    score_f1 = webhook_data.payload.teams.faction1.score
    score_f2 = webhook_data.payload.teams.faction2.score
    winner = webhook_data.payload.results.winner  # 'faction1' ou 'faction2'

    # 3. Busca a partida no banco
    partida = db.query(Partida).filter(Partida.faceit_match_id == match_id).first()
    if not partida:
        return {"status": "erro", "detalhe": "Partida não encontrada no banco."}

    # 4. Salva o placar — isso estava faltando antes, os dados chegavam e sumiam
    partida.score_a = score_f1
    partida.score_b = score_f2

    # 5. Determina o vencedor e salva no banco
    if winner == "faction1":
        partida.vencedor_id = partida.time_a_id
    else:
        partida.vencedor_id = partida.time_b_id

    # 6. Aplica a regra dos 10.000 pontos do Stadium
    # Placar 3x0: trava para validação manual do capitão (pode ter vantagem de pontos)
    if (score_f1 == 3 and score_f2 == 0) or (score_f1 == 0 and score_f2 == 3):
        partida.status = "aguardando_validacao_stadium"
        mensagem = "Placar 3x0 detectado. Aguardando print do capitão para confirmar 10.000 pontos."
    else:
        # Partida normal: fecha direto e aplica estatísticas
        partida.status = "concluida"
        partida.finalizada_em = datetime.utcnow()
        _atualizar_estatisticas(partida, db)
        mensagem = f"Partida encerrada normalmente. Placar: {score_f1}x{score_f2}."

    db.commit()
    return {"status": "sucesso", "acao": mensagem}


def _atualizar_estatisticas(partida: Partida, db: Session):
    """
    Atualiza vitórias, derrotas e saldo de mapas das equipes.
    Chamado automaticamente para partidas normais (não 3x0).
    Para 3x0, as estatísticas são aplicadas só após o admin aprovar o print.
    """
    time_a = db.query(Equipe).filter(Equipe.id == partida.time_a_id).first()
    time_b = db.query(Equipe).filter(Equipe.id == partida.time_b_id).first()

    if not time_a or not time_b:
        return

    time_a.mapas_pro += partida.score_a
    time_a.mapas_contra += partida.score_b
    time_b.mapas_pro += partida.score_b
    time_b.mapas_contra += partida.score_a

    time_a.saldo_mapas = time_a.mapas_pro - time_a.mapas_contra
    time_b.saldo_mapas = time_b.mapas_pro - time_b.mapas_contra

    if partida.vencedor_id == time_a.id:
        time_a.vitorias += 1
        time_b.derrotas += 1
    else:
        time_b.vitorias += 1
        time_a.derrotas += 1