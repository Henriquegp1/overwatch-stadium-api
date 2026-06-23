# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database.connection import Base


# --- TABELA DE USUÁRIOS ---
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    cargo = Column(String, default="capitao")  # 'admin' ou 'capitao'


# --- TABELA DE EQUIPES ---
class Equipe(Base):
    __tablename__ = "equipes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)
    nome_capitao = Column(String, nullable=False)
    email_capitao = Column(String, nullable=True)  # Para notificações futuras

    # Fase de Grupos
    grupo = Column(String, nullable=True)  # 'A', 'B', 'C', 'D', 'E'

    # Estatísticas — usadas para classificação e desempate (ver PDF seção 4)
    vitorias = Column(Integer, default=0)
    derrotas = Column(Integer, default=0)
    mapas_pro = Column(Integer, default=0)    # Mapas ganhos (ofensivo)
    mapas_contra = Column(Integer, default=0) # Mapas perdidos
    saldo_mapas = Column(Integer, default=0)  # mapas_pro - mapas_contra
    wo_count = Column(Integer, default=0)     # Punições/WO (critério disciplinar)

    # Fase atual da equipe no campeonato
    # 'inscrita' -> 'eliminatoria' -> 'grupos' -> 'playoffs' -> 'eliminada'
    fase_atual = Column(String, default="inscrita")

    # Relacionamentos
    partidas_como_time_a = relationship(
        "Partida", foreign_keys="Partida.time_a_id", back_populates="time_a"
    )
    partidas_como_time_b = relationship(
        "Partida", foreign_keys="Partida.time_b_id", back_populates="time_b"
    )


# --- TABELA DE PARTIDAS ---
class Partida(Base):
    __tablename__ = "partidas"

    id = Column(Integer, primary_key=True, index=True)
    faceit_match_id = Column(String, unique=True, index=True, nullable=True)

    # Quais equipes jogam
    time_a_id = Column(Integer, ForeignKey("equipes.id"), nullable=False)
    time_b_id = Column(Integer, ForeignKey("equipes.id"), nullable=True)  # Nullable para o caso de BYE

    # Resultado
    score_a = Column(Integer, nullable=True)   # Mapas vencidos pelo Time A
    score_b = Column(Integer, nullable=True)   # Mapas vencidos pelo Time B
    vencedor_id = Column(Integer, ForeignKey("equipes.id"), nullable=True)

    # Organização no campeonato
    # 'eliminatoria', 'grupos', 'playoffs'
    fase = Column(String, nullable=False, default="eliminatoria")
    grupo = Column(String, nullable=True)  # Só preenchido na fase de grupos: 'A'...'E'
    rodada = Column(Integer, nullable=True)

    # Fluxo de status (ver PDF seção 2 e o ponto crítico dos 10.000 pontos)
    # Valores possíveis:
    # 'agendada'                    -> Partida criada, aguardando criação na FACEIT
    # 'em_andamento'                -> Match room criada na FACEIT, jogo rolando
    # 'aguardando_validacao_stadium'-> Placar 3x0, aguarda capitão enviar print
    # 'aguardando_aprovacao_admin'  -> Capitão enviou print, admin precisa validar
    # 'validacao_concluida'         -> Admin aprovou, pontos aplicados
    # 'concluida'                   -> Partida normal finalizada (não foi 3x0)
    # 'wo'                          -> Uma equipe não compareceu
    # 'bye'                         -> Avanço automático (número ímpar de equipes)
    status = Column(String, default="agendada")

    # Print enviado pelo capitão para validação do 3x0
    print_url = Column(String, nullable=True)

    # Timestamps
    criada_em = Column(DateTime, default=datetime.utcnow)
    finalizada_em = Column(DateTime, nullable=True)

    # Relacionamentos
    time_a = relationship("Equipe", foreign_keys=[time_a_id], back_populates="partidas_como_time_a")
    time_b = relationship("Equipe", foreign_keys=[time_b_id], back_populates="partidas_como_time_b")
    vencedor = relationship("Equipe", foreign_keys=[vencedor_id])