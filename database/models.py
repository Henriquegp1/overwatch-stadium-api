from sqlalchemy import Column, Integer, String
from database.connection import Base

# --- TABELA DE USUÁRIOS (Segurança) ---
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    cargo = Column(String, default="capitao") # 'admin' ou 'capitao'

# --- TABELAS DO CAMPEONATO ---
class Equipe(Base):
    __tablename__ = "equipes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)
    nome_capitao = Column(String, nullable=False)
    saldo_mapas = Column(Integer, default=0)

class Partida(Base):
    __tablename__ = "partidas"

    id = Column(Integer, primary_key=True, index=True)
    faceit_match_id = Column(String, unique=True, index=True, nullable=True)
    time_a_id = Column(Integer)
    time_b_id = Column(Integer)
    status = Column(String, default="agendada")