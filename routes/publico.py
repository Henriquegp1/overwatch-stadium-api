# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Equipe, Partida, Jogador

router = APIRouter()


@router.get("/equipes")
def listar_equipes_publico(db: Session = Depends(get_db)):
    equipes = db.query(Equipe).order_by(Equipe.pontuacao_rank.desc()).all()
    resultado = []
    for e in equipes:
        jogadores = db.query(Jogador).filter(
            Jogador.equipe_id == e.id,
            Jogador.reserva == False
        ).all()
        resultado.append({
            "id": e.id,
            "nome": e.nome,
            "nome_capitao": e.nome_capitao,
            "grupo": e.grupo,
            "fase_atual": e.fase_atual,
            "pontuacao_rank": e.pontuacao_rank,
            "vitorias": e.vitorias,
            "derrotas": e.derrotas,
            "saldo_mapas": e.saldo_mapas,
            "tem_jogador_desclassificado": e.tem_jogador_desclassificado,
            "horarios": e.horarios,
            "dias": e.dias,
            "jogadores": [
                {"battletag": j.battletag, "role": j.role, "rank": j.rank}
                for j in jogadores
            ]
        })
    return resultado


@router.get("/partidas")
def listar_partidas_publico(db: Session = Depends(get_db)):
    partidas = db.query(Partida).order_by(Partida.criada_em.desc()).all()
    resultado = []
    for p in partidas:
        time_a = db.query(Equipe).filter(Equipe.id == p.time_a_id).first()
        time_b = db.query(Equipe).filter(Equipe.id == p.time_b_id).first() if p.time_b_id else None
        vencedor = db.query(Equipe).filter(Equipe.id == p.vencedor_id).first() if p.vencedor_id else None
        resultado.append({
            "id": p.id,
            "fase": p.fase,
            "grupo": p.grupo,
            "rodada": p.rodada,
            "status": p.status,
            "score_a": p.score_a,
            "score_b": p.score_b,
            "time_a": time_a.nome if time_a else "—",
            "time_b": time_b.nome if time_b else "BYE",
            "vencedor": vencedor.nome if vencedor else None,
            "finalizada_em": p.finalizada_em,
        })
    return resultado


@router.get("/grupos")
def classificacao_por_grupo(db: Session = Depends(get_db)):
    grupos = ["A", "B", "C", "D", "E"]
    resultado = {}
    for grupo in grupos:
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
        if equipes:
            resultado[grupo] = [
                {
                    "nome": e.nome,
                    "vitorias": e.vitorias,
                    "derrotas": e.derrotas,
                    "saldo_mapas": e.saldo_mapas,
                    "mapas_pro": e.mapas_pro,
                }
                for e in equipes
            ]
    return resultado