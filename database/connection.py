from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# Carrega as configurações do .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Configuração de segurança do motor do banco de dados
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Função segura que abre a conexão quando chega uma requisição e fecha logo em seguida
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()