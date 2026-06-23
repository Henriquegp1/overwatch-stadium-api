from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Usuario
from security.auth import gerar_hash_senha, verificar_senha, criar_token_jwt

router = APIRouter()

# --- MODELOS (O que esperamos que o usuário envie) ---
class UsuarioCriar(BaseModel):
    email: str
    senha: str
    cargo: str = "capitao" # Por padrão, quem se cadastra é capitão

class UsuarioLogin(BaseModel):
    email: str
    senha: str

# --- ROTA DE REGISTRO ---
@router.post("/registrar")
def registrar_usuario(usuario: UsuarioCriar, db: Session = Depends(get_db)):
    # 1. Verifica se o email já existe
    usuario_existente = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Este email já está cadastrado.")
    
    # 2. Cria o usuário com a senha protegida (HASH)
    novo_usuario = Usuario(
        email=usuario.email,
        senha_hash=gerar_hash_senha(usuario.senha),
        cargo=usuario.cargo
    )
    
    db.add(novo_usuario)
    db.commit()
    
    return {"status": "sucesso", "mensagem": "Conta criada com segurança!"}

# --- ROTA DE LOGIN ---
@router.post("/login")
def fazer_login(usuario: UsuarioLogin, db: Session = Depends(get_db)):
    # 1. Procura o usuário pelo email
    usuario_db = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    
    # 2. Verifica se o usuário existe e se a senha bate com o Hash
    if not usuario_db or not verificar_senha(usuario.senha, usuario_db.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos.")
    
    # 3. Se tudo estiver certo, gera o Token JWT
    token = criar_token_jwt({"sub": usuario_db.email, "cargo": usuario_db.cargo})
    
    return {
        "access_token": token, 
        "token_type": "bearer",
        "mensagem": "Login aprovado!"
    }