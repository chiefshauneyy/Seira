import os
from fastapi import FastAPI, Request
import seira_core as core
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

@app.get("/")
def read_root():
    # Adding a timestamp helps confirm the site isn't cached
    import datetime
    return {"status": "Seira API is active", "time": str(datetime.datetime.now())}

@app.post("/alexa")
async def alexa_hook(request: Request):
    data = await request.json()
    user_input = data.get("text", "")
    memory = core.load_memory()
    system = f"You are {core.AGENT_NAME} responding via Alexa. Be extremely concise."
    response = core.llm(system, f"User: {user_input}\nContext: {core.memory_summary(memory)}")
    return {"reply": response}

if __name__ == "__main__":
    import uvicorn
    # Simplified startup - letting uvicorn handle the heavy lifting
    uvicorn.run(app, host="0.0.0.0", port=8000, proxy_headers=True, forwarded_allow_ips="*")