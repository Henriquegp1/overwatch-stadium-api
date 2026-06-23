from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Configura o Bcrypt como o nosso embaralhador oficial
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

def gerar_hash_senha(senha_plana):
    """Transforma 'senha123' em um texto ilegível"""
    return pwd_context.hash(senha_plana)

def verificar_senha(senha_plana, senha_hasheada):
    """Compara a senha digitada com o hash salvo no banco"""
    return pwd_context.verify(senha_plana, senha_hasheada)

def criar_token_jwt(dados: dict):
    """Cria o passe livre digital que expira em 24 horas"""
    dados_para_codificar = dados.copy()
    expiracao = datetime.utcnow() + timedelta(hours=24)
    dados_para_codificar.update({"exp": expiracao})
    
    token_codificado = jwt.encode(dados_para_codificar, SECRET_KEY, algorithm=ALGORITHM)
    return token_codificado