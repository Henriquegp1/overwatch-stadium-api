from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database.connection import engine, Base
from database import models
from routes import webhooks
from routes import inscricoes
from routes import users
from routes import partidas
from routes import equipes

load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Overwatch Stadium API",
    description="Sistema orquestrador de partidas integrado com a FACEIT"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(users.router, prefix="/api/usuarios", tags=["Usuários"])
app.include_router(partidas.router, prefix="/api/partidas", tags=["Partidas"])
app.include_router(equipes.router, prefix="/api/equipes", tags=["Equipes"])
app.include_router(inscricoes.router, prefix="/api/inscricoes", tags=["Inscrições"])

@app.get("/")
def status_do_servidor():
    return {"status": "Online", "mensagem": "Banco de dados e Rotas conectados!"}