# -*- coding: utf-8 -*-
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database.connection import get_db
from database.models import Usuario
import os
from dotenv import load_dotenv

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

# Diz ao FastAPI onde o token chega (o frontend manda no header Authorization: Bearer <token>)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/usuarios/login")


def gerar_hash_senha(senha_plana: str) -> str:
    return pwd_context.hash(senha_plana)


def verificar_senha(senha_plana: str, senha_hasheada: str) -> bool:
    return pwd_context.verify(senha_plana, senha_hasheada)


def criar_token_jwt(dados: dict) -> str:
    dados_para_codificar = dados.copy()
    expiracao = datetime.utcnow() + timedelta(hours=24)
    dados_para_codificar.update({"exp": expiracao})
    return jwt.encode(dados_para_codificar, SECRET_KEY, algorithm=ALGORITHM)


# --- DEPENDÊNCIAS DE PROTEÇÃO DE ROTAS ---

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Lê o token JWT do header, valida e retorna o usuário logado.
    Use como dependência em qualquer rota que exija login.
    Exemplo: def minha_rota(usuario = Depends(get_current_user))
    """
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credenciais_invalidas
    except JWTError:
        raise credenciais_invalidas

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        raise credenciais_invalidas

    return usuario


def get_current_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    """
    Além de validar o token, exige que o usuário seja admin.
    Use nas rotas de aprovar/rejeitar partida.
    Exemplo: def aprovar(usuario = Depends(get_current_admin))
    """
    if usuario.cargo != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores."
        )
    return usuario