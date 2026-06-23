# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from database.connection import get_db
from database.models import Equipe
from security.auth import get_current_admin, get_current_user

router = APIRouter()


class EquipeCriar(BaseModel):
    nome: str
    nome_capitao: str
    email_capitao: Optional[str] = None


class EquipeAtualizar(BaseModel):
    grupo: Optional[str] = None
    fase_atual: Optional[str] = None


# --- LISTAGEM ---

@router.get("/")
def listar_equipes(db: Session = Depends(get_db), usuario=Depends(get_current_user)):
    return db.query(Equipe).all()


@router.get("/grupo/{grupo}")
def listar_equipes_por_grupo(
    grupo: str,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    """Retorna as equipes de um grupo ordenadas por classificação."""
    grupo = grupo.upper()
    equipes = (
        db.query(Equipe)
        .filter(Equipe.grupo == grupo)
        .order_by(
            Equipe.vitorias.desc(),
            Equipe.saldo_mapas.desc(),
            Equipe.mapas_pro.desc(),
            Equipe.wo_count.asc()
        )
        .all()
    )
    if not equipes:
        raise HTTPException(status_code=404, detail=f"Nenhuma equipe no grupo {grupo}.")
    return equipes


@router.get("/segundos-colocados")
def melhores_segundos_colocados(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    """
    Retorna os 3 melhores segundos colocados entre os 5 grupos.
    Critérios de desempate em ordem (conforme PDF seção 4):
    1. Vitórias
    2. Saldo de mapas
    3. Mapas pró (ofensivo)
    4. Menor WO
    """
    grupos = ["A", "B", "C", "D", "E"]
    segundos = []

    for grupo in grupos:
        equipes_do_grupo = (
            db.query(Equipe)
            .filter(Equipe.grupo == grupo)
            .order_by(
                Equipe.vitorias.desc(),
                Equipe.saldo_mapas.desc(),
                Equipe.mapas_pro.desc(),
                Equipe.wo_count.asc()
            )
            .all()
        )
        if len(equipes_do_grupo) >= 2:
            segundos.append(equipes_do_grupo[1])  # índice 1 = segundo colocado

    # Ordena os segundos colocados pelos mesmos critérios para pegar os 3 melhores
    segundos_ordenados = sorted(
        segundos,
        key=lambda e: (-e.vitorias, -e.saldo_mapas, -e.mapas_pro, e.wo_count)
    )

    return segundos_ordenados[:3]


# --- CADASTRO E EDIÇÃO (só admin) ---

@router.post("/")
def cadastrar_equipe(
    equipe: EquipeCriar,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    existente = db.query(Equipe).filter(Equipe.nome == equipe.nome).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe uma equipe com esse nome.")

    nova_equipe = Equipe(
        nome=equipe.nome,
        nome_capitao=equipe.nome_capitao,
        email_capitao=equipe.email_capitao
    )
    db.add(nova_equipe)
    db.commit()
    db.refresh(nova_equipe)

    return nova_equipe


@router.patch("/{equipe_id}")
def atualizar_equipe(
    equipe_id: int,
    dados: EquipeAtualizar,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Permite o admin mover equipe de grupo ou fase."""
    equipe = db.query(Equipe).filter(Equipe.id == equipe_id).first()
    if not equipe:
        raise HTTPException(status_code=404, detail="Equipe não encontrada.")

    if dados.grupo is not None:
        equipe.grupo = dados.grupo.upper()
    if dados.fase_atual is not None:
        equipe.fase_atual = dados.fase_atual

    db.commit()
    db.refresh(equipe)
    return equipe


@router.delete("/{equipe_id}")
def remover_equipe(
    equipe_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    equipe = db.query(Equipe).filter(Equipe.id == equipe_id).first()
    if not equipe:
        raise HTTPException(status_code=404, detail="Equipe não encontrada.")

    db.delete(equipe)
    db.commit()
    return {"mensagem": f"Equipe '{equipe.nome}' removida."}