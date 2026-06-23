import os
import requests
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Partida

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/")
def listar_partidas(db: Session = Depends(get_db)):
    return db.query(Partida).all()

# 1. ROTA DE UPLOAD: Salva a imagem com nome previsível (print_partida_X.png)
@router.post("/{partida_id}/upload-print")
async def receber_print_vitoria(
    partida_id: int, 
    arquivo: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
        
    nome_arquivo = f"print_partida_{partida_id}.png"
    caminho_arquivo = os.path.join(UPLOAD_DIR, nome_arquivo)
    
    with open(caminho_arquivo, "wb") as buffer:
        buffer.write(await arquivo.read())
        
    partida.status = "aguardando_aprovacao_admin"
    db.commit()
    
    return {"mensagem": "Print enviado com sucesso! Aguardando a revisão do dono da partida."}

# 2. ROTA DO ADMIN: Aprovar o resultado e entregar pontos
@router.post("/{partida_id}/aprovar")
def aprovar_partida(partida_id: int, db: Session = Depends(get_db)):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
        
    # --- INTEGRAÇÃO COM A FACEIT ---
    # Aqui o seu Python atua como o "Robô" que vai bater na porta da FACEIT
    FACEIT_API_KEY = "sua_chave_secreta_da_faceit_aqui"
    FACEIT_URL = f"https://open.faceit.com/data/v4/matches/{partida.faceit_match_id}/points"
    
    headers = {
        "Authorization": f"Bearer {FACEIT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Simulação do payload que a FACEIT pede para dar os pontos
    dados_pontuacao = {
        "points": 10000,
        "reason": "Vitória 3x0 confirmada pelo Admin Overwatch Stadium"
    }
    
    try:
        # Quando tiver a sua chave real, basta descomentar a linha abaixo para o envio acontecer de verdade!
        # resposta_faceit = requests.post(FACEIT_URL, headers=headers, json=dados_pontuacao)
        
        # print(f"Status da FACEIT: {resposta_faceit.status_code}")
        print(f"SUCESSO SIMULADO: 10.000 pontos enviados para a partida {partida.faceit_match_id}!")
        
        # Se a FACEIT confirmar, mudamos o status no nosso banco
        partida.status = "validacao_concluida"
        db.commit()
        
        return {"mensagem": "Partida aprovada e 10.000 pontos transferidos com sucesso via FACEIT!"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao comunicar com a FACEIT.")

# 3. ROTA DO ADMIN: Rejeitar o resultado
@router.post("/{partida_id}/rejeitar")
def rejeitar_partida(partida_id: int, db: Session = Depends(get_db)):
    partida = db.query(Partida).filter(Partida.id == partida_id).first()
    if not partida:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
        
    partida.status = "aguardando_validacao_stadium"
    db.commit()
    return {"mensagem": "Print rejeitado! O capitão precisará enviar uma nova imagem."}