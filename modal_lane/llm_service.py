import modal  # type:ignore

MODEL = "Qwen/Qwen3-30B-A3B"

app = modal.App("papyrus-private-llm")

# the container recipe: Debian + the libraries needed to run the model
# transformers pinned: 4.54+ rewrote model loading and silently skips 4-bit quantization
image = modal.Image.debian_slim(python_version="3.12").pip_install("torch", "transformers==4.53.2", "accelerate", "bitsandbytes", "fastapi[standard]")

# persistent disk: the ~60GB of weights download once, then live here
cache = modal.Volume.from_name("hf-cache", create_if_missing=True)


@app.cls(
    image=image,
    # 4-bit Qwen3-30B-A3B measured ~22GB+ at load; A10G (24GB) OOMs. Preference list:
    # whichever 40GB+ card Modal has capacity for right now serves the request.
    gpu=["L40S", "A100-40GB", "A100-80GB"],
    volumes={"/cache": cache},
    timeout=300,
    scaledown_window=300,
    secrets=[modal.Secret.from_name("llm-lane-token")],
)
class LLM:
    @modal.enter()
    def load(self):
        import os

        os.environ["HF_HOME"] = "/cache"
        # quantize-on-load fragments GPU memory badly; without this the A10G OOMs with ~12GB stuck in holes
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        import torch  # type:ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # type:ignore

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=quant, device_map={"": 0})

    @modal.fastapi_endpoint(method="POST")
    def generate(self, data: dict):
        import os

        if data.get("token") != os.environ["LANE_TOKEN"]:
            from fastapi import HTTPException  # type:ignore

            raise HTTPException(status_code=401, detail="unauthorized")
        prompt = data["prompt"]
        max_new_tokens = data.get("max_new_tokens", 512)

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = self.tokenizer(text, return_tensors="pt").to("cuda")
        output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        new_tokens = output[0][inputs.input_ids.shape[1] :]
        reply = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return {"text": reply}
