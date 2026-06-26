# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from database.connection import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    cargo = Column(String, default="capitao")


class Equipe(Base):
    __tablename__ = "equipes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)
    nome_capitao = Column(String, nullable=False)
    email_capitao = Column(String, nullable=True)
    grupo = Column(String, nullable=True)
    vitorias = Column(Integer, default=0)
    derrotas = Column(Integer, default=0)
    mapas_pro = Column(Integer, default=0)
    mapas_contra = Column(Integer, default=0)
    saldo_mapas = Column(Integer, default=0)
    wo_count = Column(Integer, default=0)
    fase_atual = Column(String, default="inscrita")
    faceit_team_id = Column(String, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    pontuacao_rank = Column(Integer, default=0)
    horarios = Column(JSONB, default=list)
    dias = Column(JSONB, default=list)
    tem_jogador_desclassificado = Column(Boolean, default=False)
    verificado = Column(Boolean, default=False)

    capitao = relationship("Usuario", foreign_keys=[usuario_id])
    jogadores = relationship("Jogador", back_populates="equipe")
    partidas_como_time_a = relationship(
        "Partida", foreign_keys="Partida.time_a_id", back_populates="time_a"
    )
    partidas_como_time_b = relationship(
        "Partida", foreign_keys="Partida.time_b_id", back_populates="time_b"
    )


class Partida(Base):
    __tablename__ = "partidas"

    id = Column(Integer, primary_key=True, index=True)
    faceit_match_id = Column(String, unique=True, index=True, nullable=True)
    time_a_id = Column(Integer, ForeignKey("equipes.id"), nullable=False)
    time_b_id = Column(Integer, ForeignKey("equipes.id"), nullable=True)
    score_a = Column(Integer, nullable=True)
    score_b = Column(Integer, nullable=True)
    vencedor_id = Column(Integer, ForeignKey("equipes.id"), nullable=True)
    fase = Column(String, nullable=False, default="eliminatoria")
    grupo = Column(String, nullable=True)
    rodada = Column(Integer, nullable=True)
    status = Column(String, default="agendada")
    print_url = Column(String, nullable=True)
    criada_em = Column(DateTime, default=datetime.utcnow)
    finalizada_em = Column(DateTime, nullable=True)
    streamer = Column(String, nullable=True)
    horario_agendado = Column(DateTime, nullable=True)
    modo = Column(String, default="eliminatorio")

    time_a = relationship("Equipe", foreign_keys=[time_a_id], back_populates="partidas_como_time_a")
    time_b = relationship("Equipe", foreign_keys=[time_b_id], back_populates="partidas_como_time_b")
    vencedor = relationship("Equipe", foreign_keys=[vencedor_id])


RANK_PONTOS = {
    "Bronze 5": 1, "Bronze 4": 2, "Bronze 3": 3, "Bronze 2": 4, "Bronze 1": 5,
    "Prata 5": 6, "Prata 4": 7, "Prata 3": 8, "Prata 2": 9, "Prata 1": 10,
    "Ouro 5": 11, "Ouro 4": 12, "Ouro 3": 13, "Ouro 2": 14, "Ouro 1": 15,
    "Platina 5": 16, "Platina 4": 17, "Platina 3": 18, "Platina 2": 19, "Platina 1": 20,
    "Diamante 5": 21, "Diamante 4": 22, "Diamante 3": 23, "Diamante 2": 24, "Diamante 1": 25,
    "Mestre 5": 26, "Mestre 4": 27, "Mestre 3": 28, "Mestre 2": 29, "Mestre 1": 30,
}


class Jogador(Base):
    __tablename__ = "jogadores"

    id = Column(Integer, primary_key=True, index=True)
    equipe_id = Column(Integer, ForeignKey("equipes.id"), nullable=False)
    battletag = Column(String, nullable=False)
    discord = Column(String, nullable=True)
    role = Column(String, nullable=False)
    rank = Column(String, nullable=False)
    pontos_rank = Column(Integer, nullable=False)
    reserva = Column(Boolean, default=False)

    equipe = relationship("Equipe", back_populates="jogadores")