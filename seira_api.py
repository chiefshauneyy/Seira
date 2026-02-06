import os
from fastapi import FastAPI, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
import seira_core as core
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Standard middleware to ensure the app trusts the tunnel's host
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

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
    # Use proxy_headers=True here instead of a manual middleware import
    uvicorn.run(app, host="0.0.0.0", port=8000, proxy_headers=True, forwarded_allow_ips="*")