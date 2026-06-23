# -*- coding: utf-8 -*-
import os
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from database.connection import get_db
from database.models import Partida, Equipe
from security.auth import get_current_user, get_current_admin

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class PartidaCriar(BaseModel):
    time_a_id: int
    time_b_id: Optional[int] = None  # None = BYE
    fase: str  # 'eliminatoria', 'grupos', 'playoffs'
    grupo: Optional[str] = None  # Só para fase de grupos
    rodada: Optional[int] = None


# --- LISTAGEM ---

@router.get("/")
def listar_partidas(db: Session = Depends(get_db), usuario=Depends(get_current_user)):
    return db.query(Partida).all()


# --- CRIAÇÃO (só admin) ---

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

    # BYE: avanço automático
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
        return {"mensagem": "BYE registrado. Equipe avança automaticamente.", "partida": nova_partida}

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


# --- VINCULAR ID DA FACEIT ---

@router.patch("/{partida_id}/faceit-id")
def vincular_faceit_id(
    partida_id: int,
    faceit_match_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """
    Depois de criar a sala na FACEIT, vincula o match_id aqui.
    O webhook usa esse ID para saber qual partida atualizar.
    """
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")

    partida.faceit_match_id = faceit_match_id
    partida.status = "em_andamento"
    db.commit()

    return {"mensagem": "FACEIT match ID vinculado.", "faceit_match_id": faceit_match_id}


# --- UPLOAD DE PRINT (capitão) ---

@router.post("/{partida_id}/upload-print")
async def receber_print_vitoria(
    partida_id: int,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")

    if partida.status != "aguardando_validacao_stadium":
        raise HTTPException(
            status_code=400,
            detail=f"Esta partida não está aguardando print. Status atual: {partida.status}"
        )

    nome_arquivo = f"print_partida_{partida_id}.png"
    caminho_arquivo = os.path.join(UPLOAD_DIR, nome_arquivo)

    with open(caminho_arquivo, "wb") as buffer:
        buffer.write(await arquivo.read())

    partida.print_url = f"/uploads/{nome_arquivo}"
    partida.status = "aguardando_aprovacao_admin"
    db.commit()

    return {"mensagem": "Print enviado. Aguardando revisão do admin."}


# --- APROVAR / REJEITAR (admin) ---

@router.post("/{partida_id}/aprovar")
def aprovar_partida(
    partida_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")

    if partida.status != "aguardando_aprovacao_admin":
        raise HTTPException(
            status_code=400,
            detail=f"Status atual não permite aprovação: {partida.status}"
        )

    _aplicar_resultado(partida, db)
    partida.status = "validacao_concluida"
    partida.finalizada_em = datetime.utcnow()
    db.commit()

    return {"mensagem": "Partida aprovada. Estatísticas atualizadas."}


@router.post("/{partida_id}/rejeitar")
def rejeitar_partida(
    partida_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")

    partida.status = "aguardando_validacao_stadium"
    partida.print_url = None
    db.commit()

    return {"mensagem": "Print rejeitado. Capitão deve enviar nova imagem."}


def _aplicar_resultado(partida: Partida, db: Session):
    if partida.vencedor_id is None or partida.score_a is None:
        return

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