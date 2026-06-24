# -*- coding: utf-8 -*-
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from database.connection import get_db
from database.models import Partida, Equipe
from security.auth import get_current_user, get_current_admin

router = APIRouter()


class PartidaCriar(BaseModel):
    time_a_id: int
    time_b_id: Optional[int] = None
    fase: str
    grupo: Optional[str] = None
    rodada: Optional[int] = None


@router.get("/")
def listar_partidas(db: Session = Depends(get_db), usuario=Depends(get_current_user)):
    return db.query(Partida).all()


@router.post("/")
def criar_partida(
    dados: PartidaCriar,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    time_a = db.query(Equipe).filter(Equipe.id == dados.time_a_id).first()
    if not time_a:
        raise HTTPException(status_code=404, detail=f"Equipe {dados.time_a_id} não encontrada.")

    if dados.time_b_id is not None:
        time_b = db.query(Equipe).filter(Equipe.id == dados.time_b_id).first()
        if not time_b:
            raise HTTPException(status_code=404, detail=f"Equipe {dados.time_b_id} não encontrada.")
        if dados.time_a_id == dados.time_b_id:
            raise HTTPException(status_code=400, detail="Uma equipe não pode jogar contra si mesma.")

    fases_validas = ["eliminatoria", "grupos", "playoffs"]
    if dados.fase not in fases_validas:
        raise HTTPException(status_code=400, detail=f"Fase inválida. Use: {fases_validas}")

    if dados.time_b_id is None:
        nova_partida = Partida(
            time_a_id=dados.time_a_id,
            time_b_id=None,
            fase=dados.fase,
            grupo=dados.grupo.upper() if dados.grupo else None,
            rodada=dados.rodada,
            status="bye",
            vencedor_id=dados.time_a_id,
            finalizada_em=datetime.utcnow()
        )
        db.add(nova_partida)
        time_a.vitorias += 1
        db.commit()
        db.refresh(nova_partida)
        return {"mensagem": "BYE registrado.", "partida": nova_partida}

    nova_partida = Partida(
        time_a_id=dados.time_a_id,
        time_b_id=dados.time_b_id,
        fase=dados.fase,
        grupo=dados.grupo.upper() if dados.grupo else None,
        rodada=dados.rodada,
        status="agendada"
    )
    db.add(nova_partida)
    db.commit()
    db.refresh(nova_partida)
    return nova_partida


@router.patch("/{partida_id}/faceit-id")
def vincular_faceit_id(
    partida_id: int,
    faceit_match_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")

    partida.faceit_match_id = faceit_match_id
    partida.status = "em_andamento"
    db.commit()

    return {"mensagem": "FACEIT match ID vinculado.", "faceit_match_id": faceit_match_id}