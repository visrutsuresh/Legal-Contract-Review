import modal #type:ignore

MODEL = "Qwen/Qwen2.5-3B-Instruct"
REVIEW_MODEL="Qwen/Qwen2.5-14B-Instruct"

app=modal.App("cs-private-llm")

#the container recipe: Debian + the libraries needed to run the model
image=(
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch","transformers", "accelerate","bitsandbytes", "fastapi[standard]")
)

# a persisent disk so the 6GB model downloads only once
cache =  modal.Volume.from_name("hf-cache",create_if_missing=True)

@app.cls(
    image=image,
    gpu="T4",
    volumes={"/cache": cache},
    timeout=60,
    scaledown_window=300,
    secrets=[modal.Secret.from_name("llm-lane-token")],
)

class LLM:

    @modal.enter()
    def load(self):
        import os 
        os.environ["HF_HOME"] = "/cache"
        import torch #type:ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer #type:ignore

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL, torch_dtype=torch.float16, device_map="cuda"
        )

    @modal.fastapi_endpoint(method="POST")
    def generate(self, data: dict):
        import os
        if data.get("token")!=os.environ["LANE_TOKEN"]:
            from fastapi import HTTPException
            raise HTTPException(status_code=401,detail="unauthorized")
        prompt = data ["prompt"]
        max_new_tokens = data.get("max_new_tokens", 512)

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages,tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text,return_tensors="pt").to("cuda")
        output = self.model.generate(
            **inputs, max_new_tokens=max_new_tokens,do_sample=False
        )
        new_tokens = output[0][inputs.input_ids.shape[1]:]
        reply = self.tokenizer.decode(new_tokens,skip_special_tokens=True)
        return {"text":reply}

@app.cls(
    image=image,
    gpu="A10G",
    volumes={"/cache": cache},
    timeout = 120,
    scaledown_window = 300,
    secrets = [modal.Secret.from_name("llm-lane-token")],
)
class ReviewLLM:
    @modal.enter()
    def load(self):
        import os
        os.environ["HF_HOME"] = "/cache"
        import torch #type:ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig #type:ignore

        self.tokenizer = AutoTokenizer.from_pretrained(REVIEW_MODEL)
        quant = BitsAndBytesConfig(load_in_4bit = True, bnb_4bit_compute_dtype = torch.float16)
        self.model = AutoModelForCausalLM.from_pretrained(
            REVIEW_MODEL, quantization_config=quant, device_map="auto"
        )

    @modal.fastapi_endpoint(method="POST")
    def generate(self, data: dict):
        import os
        if data.get("token") != os.environ["LANE_TOKEN"]:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="unauthorized")
        prompt = data["prompt"]
        max_new_tokens = data.get("max_new_tokens", 512)

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to("cuda")
        output = self.model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False
        )
        new_tokens = output[0][inputs.input_ids.shape[1]:]
        reply = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return {"text": reply}
