from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from database.connection import engine, Base
from database import models
from routes import webhooks
from routes import users
from routes import partidas # <--- Importa a nova rota

load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Overwatch Stadium API",
    description="Sistema orquestrador de partidas integrado com a FACEIT"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(users.router, prefix="/api/usuarios", tags=["Usuários"])
app.include_router(partidas.router, prefix="/api/partidas", tags=["Partidas"]) # <--- Conecta a rota no servidor

@app.get("/")
def status_do_servidor():
    return {"status": "Online", "mensagem": "Banco de dados e Rotas conectados!"}