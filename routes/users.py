# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Usuario
from security.auth import gerar_hash_senha, verificar_senha, criar_token_jwt, get_current_admin

router = APIRouter()


class UsuarioCriar(BaseModel):
    email: str
    senha: str
    # cargo removido daqui — qualquer um mandava {"cargo": "admin"} e virava admin


class UsuarioCriarAdmin(BaseModel):
    email: str
    senha: str
    cargo: str  # Só o admin pode definir cargo ao criar outro usuário


class UsuarioLogin(BaseModel):
    email: str
    senha: str


# Registro público — sempre cria como capitão
@router.post("/registrar")
def registrar_usuario(usuario: UsuarioCriar, db: Session = Depends(get_db)):
    usuario_existente = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Este email já está cadastrado.")

    novo_usuario = Usuario(
        email=usuario.email,
        senha_hash=gerar_hash_senha(usuario.senha),
        cargo="capitao"  # Fixo — sem possibilidade de manipulação
    )

    db.add(novo_usuario)
    db.commit()

    return {"status": "sucesso", "mensagem": "Conta criada como capitão."}


# Criação de usuário pelo admin — pode definir cargo
@router.post("/admin/criar-usuario")
def admin_criar_usuario(
    usuario: UsuarioCriarAdmin,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    usuario_existente = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Este email já está cadastrado.")

    if usuario.cargo not in ["admin", "capitao"]:
        raise HTTPException(status_code=400, detail="Cargo inválido. Use 'admin' ou 'capitao'.")

    novo_usuario = Usuario(
        email=usuario.email,
        senha_hash=gerar_hash_senha(usuario.senha),
        cargo=usuario.cargo
    )

    db.add(novo_usuario)
    db.commit()

    return {"status": "sucesso", "mensagem": f"Usuário criado com cargo '{usuario.cargo}'."}


@router.post("/login")
def fazer_login(usuario: UsuarioLogin, db: Session = Depends(get_db)):
    usuario_db = db.query(Usuario).filter(Usuario.email == usuario.email).first()

    if not usuario_db or not verificar_senha(usuario.senha, usuario_db.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos.")

    token = criar_token_jwt({"sub": usuario_db.email, "cargo": usuario_db.cargo})

    return {
        "access_token": token,
        "token_type": "bearer"
    }