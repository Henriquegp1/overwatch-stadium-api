# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Equipe, Partida
from security.auth import get_current_admin
from datetime import datetime
from typing import Optional

router = APIRouter()

class PartidaInfoForm(BaseModel):
    streamer: Optional[str] = None  # "akiralegacy", "foythtv", "violetkill" ou None
    horario_agendado: Optional[str] = None  # ISO string ex: "2026-06-25T20:00:00"

class VencedorForm(BaseModel):
    vencedor_id: int
    score_a: int  # mapas do time_a
    score_b: int  # mapas do time_b

@router.post("/gerar")
def gerar_chaveamento(
    forcar: bool = Query(False),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    # Verifica se já existe chaveamento ativo
    partidas_ativas = db.query(Partida).filter(
        Partida.status == "agendada"
    ).all()

    if partidas_ativas and not forcar:
        raise HTTPException(
            status_code=409,
            detail="Chaveamento já existe. Envie ?forcar=true para recriar."
        )

    # Descobre a rodada atual
    ultima_rodada = db.query(Partida).order_by(Partida.rodada.desc()).first()
    rodada_atual = 1 if not ultima_rodada else (ultima_rodada.rodada or 0) + 1

    # Primeira rodada: equipes inscritas
    # Rodadas seguintes: vencedores da rodada anterior
    if rodada_atual == 1:
        equipes = (
            db.query(Equipe)
            .filter(Equipe.fase_atual == "inscrita")
            .order_by(Equipe.pontuacao_rank.desc())
            .all()
        )
    else:
        # Pega vencedores da rodada anterior
        partidas_anteriores = db.query(Partida).filter(
            Partida.rodada == rodada_atual - 1,
            Partida.status == "concluida"
        ).all()

        # Verifica se todas as partidas da rodada anterior foram concluídas
        total_anteriores = db.query(Partida).filter(
            Partida.rodada == rodada_atual - 1
        ).count()

        if len(partidas_anteriores) < total_anteriores:
            raise HTTPException(
                status_code=400,
                detail=f"Ainda há partidas da rodada {rodada_atual - 1} não concluídas."
            )

        ids_vencedores = [
            p.vencedor_id for p in partidas_anteriores if p.vencedor_id
        ]

        # Inclui equipes que receberam BYE (time_b_id == None avança automaticamente)
        byes = db.query(Partida).filter(
            Partida.rodada == rodada_atual - 1,
            Partida.time_b_id == None  # noqa
        ).all()
        ids_vencedores += [p.time_a_id for p in byes]

        equipes = (
            db.query(Equipe)
            .filter(Equipe.fase_atual.in_(["inscrita", "eliminatoria"]))
            .order_by(Equipe.pontuacao_rank.desc())
            .all()
        )

    if len(equipes) < 2:
        raise HTTPException(
            status_code=400,
            detail="Equipes insuficientes para gerar chaveamento."
        )

    # Se forcar, apaga partidas agendadas da rodada atual
    if forcar:
        db.query(Partida).filter(
            Partida.rodada == rodada_atual,
            Partida.status == "agendada"
        ).delete()

    # Gera os confrontos
    partidas_criadas = []
    i = 0
    total = len(equipes)

    # Se ímpar, equipe do meio recebe BYE
    bye_idx = total // 2 if total % 2 != 0 else None

    indices = list(range(total))
    if bye_idx is not None:
        indices.pop(bye_idx)
        equipe_bye = equipes[bye_idx]
        # Cria partida de BYE
        partida_bye = Partida(
            time_a_id=equipe_bye.id,
            time_b_id=None,
            fase="eliminatoria",
            rodada=rodada_atual,
            status="agendada"
        )
        db.add(partida_bye)
        partidas_criadas.append({
            "time_a": equipe_bye.nome,
            "time_b": "BYE",
            "rodada": rodada_atual
        })

    equipes_filtradas = [equipes[i] for i in indices]

    for j in range(0, len(equipes_filtradas), 2):
        time_a = equipes_filtradas[j]
        time_b = equipes_filtradas[j + 1]
        partida = Partida(
            time_a_id=time_a.id,
            time_b_id=time_b.id,
            fase="eliminatoria",
            rodada=rodada_atual,
            status="agendada"
        )
        db.add(partida)
        partidas_criadas.append({
            "time_a": time_a.nome,
            "time_b": time_b.nome,
            "rodada": rodada_atual
        })

    # Atualiza fase das equipes
    for equipe in equipes:
        equipe.fase_atual = "eliminatoria"

    db.commit()

    return {
        "mensagem": f"Rodada {rodada_atual} gerada com {len(partidas_criadas)} confrontos.",
        "rodada": rodada_atual,
        "confrontos": partidas_criadas
    }


@router.patch("/partidas/{partida_id}/vencedor")
def registrar_vencedor(
    partida_id: int,
    dados: VencedorForm,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")

    # Se já foi concluída, reverte os stats antes de recalcular
    if partida.status == "concluida" and partida.score_a is not None and partida.score_b is not None:
        # Reverte vitorias/derrotas do resultado anterior
        vencedor_anterior = db.query(Equipe).filter(Equipe.id == partida.vencedor_id).first()
        perdedor_anterior_id = partida.time_b_id if partida.vencedor_id == partida.time_a_id else partida.time_a_id
        perdedor_anterior = db.query(Equipe).filter(Equipe.id == perdedor_anterior_id).first() if perdedor_anterior_id else None

        if vencedor_anterior:
            vencedor_anterior.vitorias = max(0, vencedor_anterior.vitorias - 1)
        if perdedor_anterior:
            perdedor_anterior.derrotas = max(0, perdedor_anterior.derrotas - 1)

        # Reverte saldo de mapas se não for mata-mata
        if partida.fase != "eliminatoria":
            time_a_eq = db.query(Equipe).filter(Equipe.id == partida.time_a_id).first()
            time_b_eq = db.query(Equipe).filter(Equipe.id == partida.time_b_id).first() if partida.time_b_id else None
            if time_a_eq:
                time_a_eq.saldo_mapas = (time_a_eq.saldo_mapas or 0) - (partida.score_a - partida.score_b)
                time_a_eq.mapas_pro = (time_a_eq.mapas_pro or 0) - partida.score_a
                time_a_eq.mapas_contra = (time_a_eq.mapas_contra or 0) - partida.score_b
            if time_b_eq:
                time_b_eq.saldo_mapas = (time_b_eq.saldo_mapas or 0) - (partida.score_b - partida.score_a)
                time_b_eq.mapas_pro = (time_b_eq.mapas_pro or 0) - partida.score_b
                time_b_eq.mapas_contra = (time_b_eq.mapas_contra or 0) - partida.score_a

    ids_validos = [partida.time_a_id]
    if partida.time_b_id:
        ids_validos.append(partida.time_b_id)

    if dados.vencedor_id not in ids_validos:
        raise HTTPException(
            status_code=400,
            detail="Vencedor deve ser um dos times da partida."
        )

    # Salva placar
    partida.score_a = dados.score_a
    partida.score_b = dados.score_b
    partida.vencedor_id = dados.vencedor_id
    partida.status = "concluida"

    # Atualiza vitorias/derrotas
    vencedor_equipe = db.query(Equipe).filter(Equipe.id == dados.vencedor_id).first()
    perdedor_id = partida.time_b_id if dados.vencedor_id == partida.time_a_id else partida.time_a_id
    perdedor_equipe = db.query(Equipe).filter(Equipe.id == perdedor_id).first() if perdedor_id else None

    # Se modo eliminatório, marca perdedor como eliminado
    if partida.modo == "eliminatorio" and perdedor_equipe:
        perdedor_equipe.fase_atual = "eliminado"

    if vencedor_equipe:
        vencedor_equipe.vitorias += 1

    if perdedor_equipe:
        perdedor_equipe.derrotas += 1

    # Saldo de mapas — só acumula em fase de grupos, não no mata-mata
    if partida.fase != "eliminatoria":
        saldo_a = dados.score_a - dados.score_b
        saldo_b = dados.score_b - dados.score_a

        time_a_equipe = db.query(Equipe).filter(Equipe.id == partida.time_a_id).first()
        time_b_equipe = db.query(Equipe).filter(Equipe.id == partida.time_b_id).first() if partida.time_b_id else None

        if time_a_equipe:
            time_a_equipe.saldo_mapas = (time_a_equipe.saldo_mapas or 0) + saldo_a
            time_a_equipe.mapas_pro = (time_a_equipe.mapas_pro or 0) + dados.score_a
            time_a_equipe.mapas_contra = (time_a_equipe.mapas_contra or 0) + dados.score_b

        if time_b_equipe:
            time_b_equipe.saldo_mapas = (time_b_equipe.saldo_mapas or 0) + saldo_b
            time_b_equipe.mapas_pro = (time_b_equipe.mapas_pro or 0) + dados.score_b
            time_b_equipe.mapas_contra = (time_b_equipe.mapas_contra or 0) + dados.score_a

    db.commit()
    db.refresh(partida)

    vencedor = db.query(Equipe).filter(Equipe.id == dados.vencedor_id).first()
    return {
        "mensagem": f"Vencedor '{vencedor.nome}' registrado. Placar: {dados.score_a}×{dados.score_b}",
        "partida_id": partida_id,
        "vencedor_id": dados.vencedor_id,
        "score_a": dados.score_a,
        "score_b": dados.score_b
    }


@router.get("/rodadas")
def listar_rodadas(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Retorna todas as partidas agrupadas por rodada."""
    partidas = db.query(Partida).order_by(Partida.rodada, Partida.id).all()

    rodadas: dict = {}
    for p in partidas:
        r = str(p.rodada or 1)
        if r not in rodadas:
            rodadas[r] = []

        time_a = db.query(Equipe).filter(Equipe.id == p.time_a_id).first()
        time_b = db.query(Equipe).filter(Equipe.id == p.time_b_id).first() if p.time_b_id else None
        vencedor = db.query(Equipe).filter(Equipe.id == p.vencedor_id).first() if p.vencedor_id else None

        rodadas[r].append({
            "id": p.id,
            "time_a": {"id": time_a.id, "nome": time_a.nome} if time_a else None,
            "time_b": {"id": time_b.id, "nome": time_b.nome} if time_b else {"id": None, "nome": "BYE"},
            "vencedor": {"id": vencedor.id, "nome": vencedor.nome} if vencedor else None,
            "status": p.status,
            "rodada": p.rodada,
            "score_a": p.score_a,
            "score_b": p.score_b,
            "streamer": p.streamer,
            "horario_agendado": p.horario_agendado.isoformat() if p.horario_agendado else None,
        })

    return rodadas

@router.delete("/reset")
def resetar_chaveamento(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    # Deleta todas as partidas
    db.query(Partida).delete()

    # Reseta todas as equipes
    equipes = db.query(Equipe).all()
    for e in equipes:
        e.fase_atual = "inscrita"
        e.vitorias = 0
        e.derrotas = 0
        e.saldo_mapas = 0
        e.mapas_pro = 0
        e.mapas_contra = 0
        e.wo_count = 0

    db.commit()
    return {"mensagem": "Chaveamento resetado. Todas as equipes voltaram para 'inscrita'."}

@router.patch("/partidas/{partida_id}/info")
def atualizar_info_partida(
    partida_id: int,
    dados: PartidaInfoForm,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")

    if dados.streamer is not None:
        partida.streamer = dados.streamer if dados.streamer != "" else None
    if dados.horario_agendado is not None:
        partida.horario_agendado = (
            datetime.fromisoformat(dados.horario_agendado)
            if dados.horario_agendado != ""
            else None
        )

    db.commit()
    return {"mensagem": "Informações da partida atualizadas."}

@router.patch("/equipes/{equipe_id}/reativar")
def reativar_equipe(
    equipe_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    equipe = db.query(Equipe).filter(Equipe.id == equipe_id).first()
    if not equipe:
        raise HTTPException(status_code=404, detail="Equipe não encontrada.")
    equipe.fase_atual = "eliminatoria"
    db.commit()
    return {"mensagem": f"Equipe '{equipe.nome}' reativada."}