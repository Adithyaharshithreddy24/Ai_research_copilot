from fastapi import FastAPI
from api.routes import auth, chat, actions,workspace

app = FastAPI(title="Research Co-Pilot")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://127.0.0.1:8000"]
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
    return {"message": "Research Co-Pilot Backend Running 🚀"}