# -*- coding: utf-8 -*-
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import os

from database.connection import get_db
from database.models import Partida, Equipe

router = APIRouter()


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


@router.post("/faceit")
def receber_webhook_faceit(
    webhook_data: FaceitWebhook,
    x_faceit_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    secret = os.getenv("FACEIT_WEBHOOK_SECRET")
    if not secret or x_faceit_signature != secret:
        raise HTTPException(status_code=401, detail="Assinatura inválida.")

    if webhook_data.event != "match_status_finished":
        return {"status": "ignorado", "evento": webhook_data.event}

    match_id = webhook_data.match_id
    score_f1 = webhook_data.payload.teams.faction1.score
    score_f2 = webhook_data.payload.teams.faction2.score
    winner = webhook_data.payload.results.winner

    partida = db.query(Partida).filter(Partida.faceit_match_id == match_id).first()
    if not partida:
        return {"status": "erro", "detalhe": "Partida não encontrada no banco."}

    partida.score_a = score_f1
    partida.score_b = score_f2

    if winner == "faction1":
        partida.vencedor_id = partida.time_a_id
    else:
        partida.vencedor_id = partida.time_b_id

    partida.status = "concluida"
    partida.finalizada_em = datetime.utcnow()
    _atualizar_estatisticas(partida, db)

    db.commit()
    return {"status": "sucesso", "acao": f"Partida encerrada. Placar: {score_f1}x{score_f2}."}


def _atualizar_estatisticas(partida: Partida, db: Session):
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