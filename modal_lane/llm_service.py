import modal  # type:ignore

# Qwen3-30B-A3B abandoned 2026-07-24: its 4-6 min load could never fit a request
# window (cold calls died at every timeout ceiling) and it forced $2/hr 40GB+ cards.
# vLLM swap 2026-07-28 (TODO 23.5): transformers generated one request at a time, so
# parallel inspectors queued the full length of each other's generations. vLLM
# continuous-batches, so one warm A10G serves N callers at once. Same model family,
# AWQ 4-bit instead of bitsandbytes because vLLM runs AWQ natively and fast.
MODEL = "Qwen/Qwen2.5-14B-Instruct-AWQ"

app = modal.App("papyrus-private-llm")

# transformers pinned: 4.56+ removed tokenizer attrs vllm 0.10.2 still reads
image = modal.Image.debian_slim(python_version="3.12").pip_install("vllm==0.10.2", "transformers==4.55.2", "fastapi[standard]")

# persistent disk: weights download once, then live here
cache = modal.Volume.from_name("hf-cache", create_if_missing=True)


@app.cls(
    image=image,
    gpu="A10G",  # AWQ 14B is ~10GB, fits with room for KV
    volumes={"/cache": cache},
    timeout=600,
    scaledown_window=300,  # 5 warm minutes; re-warming costs ~60s, not 5 min
    max_containers=1,  # concurrency now lives INSIDE the one container; never a second bill
    secrets=[modal.Secret.from_name("llm-lane-token")],
)
@modal.concurrent(max_inputs=8)  # the whole point of the swap: 8 callers share one GPU
class LLM:
    @modal.enter()
    def load(self):
        import os

        os.environ["HF_HOME"] = "/cache"
        from transformers import AutoTokenizer  # type:ignore
        from vllm.engine.arg_utils import AsyncEngineArgs  # type:ignore

        try:  # vllm moved the async engine in v1; take whichever this build ships
            from vllm.v1.engine.async_llm import AsyncLLM as Engine  # type:ignore
        except ImportError:
            from vllm import AsyncLLMEngine as Engine  # type:ignore

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        self.engine = Engine.from_engine_args(
            AsyncEngineArgs(
                model=MODEL,
                max_model_len=16384,
                gpu_memory_utilization=0.90,
                enforce_eager=True,  # skips CUDA-graph capture: ~1 min faster cold start, slight throughput cost
            )
        )

    @modal.fastapi_endpoint(method="POST")
    async def generate(self, data: dict):
        import os
        import uuid

        if data.get("token") != os.environ["LANE_TOKEN"]:
            from fastapi import HTTPException  # type:ignore

            raise HTTPException(status_code=401, detail="unauthorized")
        from vllm import SamplingParams  # type:ignore

        prompt = data["prompt"]
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        params = SamplingParams(temperature=0.0, max_tokens=data.get("max_new_tokens", 512))

        reply = ""
        async for out in self.engine.generate(text, params, uuid.uuid4().hex):
            reply = out.outputs[0].text  # each yield carries the full text so far; keep the last
        return {"text": reply}
