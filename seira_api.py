import os
from fastapi import FastAPI, Request
import seira_core as core
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Seira API is active"}

@app.post("/alexa")
async def alexa_hook(request: Request):
    """Endpoint for future Alexa Skill integration."""
    data = await request.json()
    user_input = data.get("text", "")
    
    memory = core.load_memory()
    system = f"You are {core.AGENT_NAME} responding via Alexa. Be extremely concise and tactical."
    response = core.llm(system, f"User via Alexa: {user_input}\nContext: {core.memory_summary(memory)}")
    
    return {"reply": response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)