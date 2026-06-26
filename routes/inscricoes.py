# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from database.connection import get_db
from database.models import Equipe, Jogador, Usuario, RANK_PONTOS
from security.auth import get_current_admin
from passlib.context import CryptContext

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RANK_MAXIMO = "Mestre 1"
RANKS_VALIDOS = list(RANK_PONTOS.keys())


class JogadorForm(BaseModel):
    battletag: str
    role: str
    rank: str
    discord: Optional[str] = None


class InscricaoForm(BaseModel):
    nome_equipe: str
    battletag_capitao: str
    discord_capitao: Optional[str] = None
    email_capitao: Optional[str] = None
    senha_temporaria: Optional[str] = None
    jogadores: List[JogadorForm]  # exatamente 5
    reservas: Optional[List[JogadorForm]] = []  # 0, 1 ou 2
    horarios: Optional[List[str]] = []  # ex: ["manha", "tarde"]
    dias: Optional[List[str]] = []      # ex: ["sabado", "domingo"]


@router.post("/")
def registrar_inscricao(
    dados: InscricaoForm,
    db: Session = Depends(get_db)
):
    # 1. Valida número de jogadores
    if len(dados.jogadores) != 5:
        raise HTTPException(status_code=400, detail="A equipe precisa ter exatamente 5 jogadores titulares.")

    if len(dados.reservas) > 2:
        raise HTTPException(status_code=400, detail="Máximo de 2 reservas permitido.")

    # 2. Verifica nome duplicado
    if db.query(Equipe).filter(Equipe.nome == dados.nome_equipe).first():
        raise HTTPException(status_code=400, detail="Já existe uma equipe com esse nome.")

    # 3. Verifica se algum jogador está acima do rank máximo
    todos_jogadores = dados.jogadores + dados.reservas
    tem_desclassificado = False

    for j in todos_jogadores:
        if j.rank not in RANKS_VALIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Rank inválido: '{j.rank}'. Use o formato exato, ex: 'Ouro 3'."
            )
        # Rank acima de Mestre 1 não existe em RANK_PONTOS — mas se vier via Forms
        # com valor fora da lista, já cai no erro acima.
        # Aqui marcamos desclassificado se pontos > 30 (caso futuro)
        if RANK_PONTOS[j.rank] > RANK_PONTOS[RANK_MAXIMO]:
            tem_desclassificado = True

    # 4. Cria usuário do capitão se email fornecido
    usuario_id = None
    if dados.email_capitao:
        existente = db.query(Usuario).filter(Usuario.email == dados.email_capitao).first()
        if existente:
            raise HTTPException(status_code=400, detail="Já existe um usuário com esse email.")

        senha = dados.senha_temporaria or dados.nome_equipe.lower().replace(" ", "")
        novo_usuario = Usuario(
            email=dados.email_capitao,
            senha_hash=pwd_context.hash(senha),
            cargo="capitao"
        )
        db.add(novo_usuario)
        db.flush()
        usuario_id = novo_usuario.id

    # 5. Calcula pontuação da equipe (só titulares)
    pontuacao = sum(RANK_PONTOS[j.rank] for j in dados.jogadores)

    # 6. Cria a equipe
    nova_equipe = Equipe(
        nome=dados.nome_equipe,
        nome_capitao=dados.battletag_capitao,
        email_capitao=dados.email_capitao,
        usuario_id=usuario_id,
        pontuacao_rank=pontuacao,
        horarios=dados.horarios,
        dias=dados.dias,
        tem_jogador_desclassificado=tem_desclassificado
    )
    db.add(nova_equipe)
    db.flush()

    # 7. Cria os jogadores
    for j in dados.jogadores:
        db.add(Jogador(
            equipe_id=nova_equipe.id,
            battletag=j.battletag,
            discord=j.discord,
            role=j.role.lower(),
            rank=j.rank,
            pontos_rank=RANK_PONTOS[j.rank],
            reserva=False
        ))

    for j in dados.reservas:
        db.add(Jogador(
            equipe_id=nova_equipe.id,
            battletag=j.battletag,
            discord=j.discord,
            role=j.role.lower(),
            rank=j.rank,
            pontos_rank=RANK_PONTOS[j.rank],
            reserva=True
        ))

    db.commit()
    db.refresh(nova_equipe)

    return {
        "mensagem": f"Equipe '{nova_equipe.nome}' inscrita com sucesso.",
        "equipe_id": nova_equipe.id,
        "pontuacao_rank": pontuacao,
        "tem_jogador_desclassificado": tem_desclassificado
    }


@router.get("/")
def listar_inscricoes(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Lista todas as equipes com seus jogadores — visão admin."""
    equipes = db.query(Equipe).all()
    resultado = []

    for equipe in equipes:
        jogadores = db.query(Jogador).filter(Jogador.equipe_id == equipe.id).all()
        resultado.append({
            "id": equipe.id,
            "nome": equipe.nome,
            "nome_capitao": equipe.nome_capitao,
            "pontuacao_rank": equipe.pontuacao_rank,
            "tem_jogador_desclassificado": equipe.tem_jogador_desclassificado,
            "verificado": equipe.verificado,      
            "fase_atual": equipe.fase_atual,      
            "horarios": equipe.horarios,
            "dias": equipe.dias,
            "jogadores": [
                {
                    "battletag": j.battletag,
                    "role": j.role,
                    "rank": j.rank,
                    "pontos_rank": j.pontos_rank,
                    "reserva": j.reserva,
                    "desclassificado": j.pontos_rank > RANK_PONTOS[RANK_MAXIMO]
                }
                for j in jogadores
            ]
        })

    return resultado

@router.patch("/{equipe_id}/verificar")
def verificar_inscricao(
    equipe_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    equipe = db.query(Equipe).filter(Equipe.id == equipe_id).first()
    if not equipe:
        raise HTTPException(status_code=404, detail="Equipe não encontrada.")
    equipe.verificado = not equipe.verificado  # toggle
    db.commit()
    return {"verificado": equipe.verificado}

class JogadorEditForm(BaseModel):
    battletag: str
    role: str
    rank: str
    discord: Optional[str] = None

class InscricaoEditForm(BaseModel):
    nome_equipe: Optional[str] = None
    battletag_capitao: Optional[str] = None
    horarios: Optional[List[str]] = None
    dias: Optional[List[str]] = None
    jogadores: Optional[List[JogadorEditForm]] = None
    reservas: Optional[List[JogadorEditForm]] = None


@router.patch("/{equipe_id}")
def editar_inscricao(
    equipe_id: int,
    dados: InscricaoEditForm,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    equipe = db.query(Equipe).filter(Equipe.id == equipe_id).first()
    if not equipe:
        raise HTTPException(status_code=404, detail="Equipe não encontrada.")

    if dados.nome_equipe:
        equipe.nome = dados.nome_equipe
    if dados.battletag_capitao:
        equipe.nome_capitao = dados.battletag_capitao
    if dados.horarios is not None:
        equipe.horarios = dados.horarios
    if dados.dias is not None:
        equipe.dias = dados.dias

    # Atualiza jogadores se enviados
    todos = (dados.jogadores or []) + (dados.reservas or [])
    if todos:
        jogadores_db = db.query(Jogador).filter(Jogador.equipe_id == equipe_id).all()
        titulares_db = [j for j in jogadores_db if not j.reserva]
        reservas_db  = [j for j in jogadores_db if j.reserva]

        for i, j in enumerate(dados.jogadores or []):
            if j.rank not in RANKS_VALIDOS:
                raise HTTPException(status_code=400, detail=f"Rank inválido: '{j.rank}'")
            if i < len(titulares_db):
                titulares_db[i].battletag  = j.battletag
                titulares_db[i].role       = j.role.lower()
                titulares_db[i].rank       = j.rank
                titulares_db[i].pontos_rank = RANK_PONTOS[j.rank]
                titulares_db[i].discord    = j.discord

        for i, j in enumerate(dados.reservas or []):
            if j.rank not in RANKS_VALIDOS:
                raise HTTPException(status_code=400, detail=f"Rank inválido: '{j.rank}'")
            if i < len(reservas_db):
                reservas_db[i].battletag  = j.battletag
                reservas_db[i].role       = j.role.lower()
                reservas_db[i].rank       = j.rank
                reservas_db[i].pontos_rank = RANK_PONTOS[j.rank]
                reservas_db[i].discord    = j.discord

        # Recalcula pontuação da equipe
        equipe.pontuacao_rank = sum(
            RANK_PONTOS[j.rank] for j in (dados.jogadores or [])
        )

        # Verifica desclassificados
        equipe.tem_jogador_desclassificado = any(
            RANK_PONTOS[j.rank] > RANK_PONTOS[RANK_MAXIMO]
            for j in todos
            if j.rank in RANK_PONTOS
        )

    db.commit()
    db.refresh(equipe)
    return {"mensagem": "Equipe atualizada com sucesso.", "equipe_id": equipe.id}