# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Equipe, Partida
from security.auth import get_current_admin

router = APIRouter()


class VencedorForm(BaseModel):
    vencedor_id: int


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
            .filter(Equipe.id.in_(ids_vencedores))
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

    if partida.status == "concluida":
        raise HTTPException(status_code=400, detail="Partida já foi concluída.")

    # Valida que o vencedor é um dos times da partida
    ids_validos = [partida.time_a_id]
    if partida.time_b_id:
        ids_validos.append(partida.time_b_id)

    if dados.vencedor_id not in ids_validos:
        raise HTTPException(
            status_code=400,
            detail="Vencedor deve ser um dos times da partida."
        )

    partida.vencedor_id = dados.vencedor_id
    partida.status = "concluida"

    vencedor_equipe = db.query(Equipe).filter(Equipe.id == dados.vencedor_id).first()
    perdedor_id = partida.time_b_id if dados.vencedor_id == partida.time_a_id else partida.time_a_id
    perdedor_equipe = db.query(Equipe).filter(Equipe.id == perdedor_id).first() if perdedor_id else None

    if vencedor_equipe:
        vencedor_equipe.vitorias += 1
    if perdedor_equipe:
        perdedor_equipe.derrotas += 1

    db.commit()
    db.refresh(partida)

    vencedor = db.query(Equipe).filter(Equipe.id == dados.vencedor_id).first()
    return {
        "mensagem": f"Vencedor '{vencedor.nome}' registrado.",
        "partida_id": partida_id,
        "vencedor_id": dados.vencedor_id
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
            "rodada": p.rodada
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