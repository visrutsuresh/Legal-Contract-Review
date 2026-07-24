# local_lane.py — $0 stand-in for the Modal lane, same wire protocol.
# Fronts a local Ollama model so the bench can run with no GPU credit at all.
#
#   uv run uvicorn modal_lane.local_lane:app --port 8899
#
# then run the app/bench with the lane pointed here (no .env change needed;
# real env vars beat the .env file):
#
#   PRIVATE_LANE_URL=http://127.0.0.1:8899 PRIVATE_LANE_TOKEN=local uv run python bench.py --only kestrel
import json
import os
import time

from fastapi import FastAPI, HTTPException
import requests

app = FastAPI()

# optional call log for tuning sessions: set LANE_LOG=/path/to/file.jsonl
LANE_LOG = os.environ.get("LANE_LOG")

OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:14b"  # same family/size as the deployed Modal lane


@app.post("/")
def generate(data: dict):
    if data.get("token") != "local":
        raise HTTPException(status_code=401, detail="unauthorized")
    r = requests.post(
        OLLAMA_CHAT,
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": data["prompt"]}],
            "stream": False,
            "options": {
                "num_predict": data.get("max_new_tokens", 512),
                "temperature": 0,  # match the Modal lane's do_sample=False
                "num_ctx": 16384,  # clause sheets + react transcripts overflow the 4k default
            },
        },
        timeout=880,
    )
    r.raise_for_status()
    reply = r.json()["message"]["content"]
    if LANE_LOG:
        with open(LANE_LOG, "a") as fh:
            fh.write(json.dumps({"t": time.time(), "prompt": data["prompt"], "reply": reply}) + "\n")
    return {"text": reply}
