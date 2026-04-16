from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import actions, auth, chat, workspace

app = FastAPI(title="Research Co-Pilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(chat.router, prefix="/chat")
app.include_router(actions.router, prefix="/actions")
app.include_router(workspace.router)


@app.get("/")
def root():
    return {"message": "Research Co-Pilot Backend Running"}
