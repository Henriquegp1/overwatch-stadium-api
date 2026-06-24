# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from passlib.context import CryptContext

from database.connection import get_db
from database.models import Equipe, Usuario
from security.auth import get_current_admin, get_current_user

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EquipeCriar(BaseModel):
    nome: str
    nome_capitao: str
    email_capitao: str  # Agora obrigatório — vai criar o usuário
    senha_temporaria: str  # Admin define uma senha inicial pro capitão


class EquipeAtualizar(BaseModel):
    grupo: Optional[str] = None
    fase_atual: Optional[str] = None
    faceit_team_id: Optional[str] = None  # Admin preenche quando o Hub for aprovado


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
            segundos.append(equipes_do_grupo[1])

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
    # Verifica nome duplicado
    if db.query(Equipe).filter(Equipe.nome == equipe.nome).first():
        raise HTTPException(status_code=400, detail="Já existe uma equipe com esse nome.")

    # Verifica email duplicado
    if db.query(Usuario).filter(Usuario.email == equipe.email_capitao).first():
        raise HTTPException(status_code=400, detail="Já existe um usuário com esse email.")

    # Cria o usuário do capitão
    novo_usuario = Usuario(
        email=equipe.email_capitao,
        senha_hash=pwd_context.hash(equipe.senha_temporaria),
        cargo="capitao"
    )
    db.add(novo_usuario)
    db.flush()  # Gera o ID sem commitar ainda

    # Cria a equipe já linkada ao usuário
    nova_equipe = Equipe(
        nome=equipe.nome,
        nome_capitao=equipe.nome_capitao,
        email_capitao=equipe.email_capitao,
        usuario_id=novo_usuario.id
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
    equipe = db.query(Equipe).filter(Equipe.id == equipe_id).first()
    if not equipe:
        raise HTTPException(status_code=404, detail="Equipe não encontrada.")

    if dados.grupo is not None:
        equipe.grupo = dados.grupo.upper()
    if dados.fase_atual is not None:
        equipe.fase_atual = dados.fase_atual
    if dados.faceit_team_id is not None:
        equipe.faceit_team_id = dados.faceit_team_id

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