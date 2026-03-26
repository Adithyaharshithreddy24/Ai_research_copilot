from fastapi import FastAPI
from api.routes import auth, chat, actions

app = FastAPI(title="Research Co-Pilot")

app.include_router(auth.router, prefix="/auth")
app.include_router(chat.router, prefix="/chat")
app.include_router(actions.router, prefix="/actions")

@app.get("/")
def root():
    return {"message": "Research Co-Pilot Backend Running 🚀"}