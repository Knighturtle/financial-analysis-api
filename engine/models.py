
import os
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from threading import Lock

class ModelManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"INFO: ModelManager initialized. Device: {self.device}")
        
        self._finbert_pipeline = None
        self._llm_model = None
        self._llm_tokenizer = None
        self._initialized = True

    def get_finbert(self):
        """
        Lazy loads ProsusAI/finbert pipeline.
        """
        if self._finbert_pipeline is None:
            print("INFO: Loading FinBERT model (ProsusAI/finbert)...")
            try:
                # Use pipeline for simplicity
                # device=0 for GPU, -1 for CPU
                device_id = 0 if self.device == "cuda" else -1
                self._finbert_pipeline = pipeline(
                    "text-classification", 
                    model="ProsusAI/finbert", 
                    device=device_id,
                    return_all_scores=True
                )
                print("INFO: FinBERT loaded successfully.")
            except Exception as e:
                print(f"ERROR: Failed to load FinBERT: {e}")
                raise e
        return self._finbert_pipeline

    def get_llm(self):
        """
        Lazy loads LLM with 4-bit quantization if configured.
        """
        if self._llm_model is None:
            model_name = os.getenv("HF_LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
            print(f"INFO: Loading LLM ({model_name})... This may take a while.")
            
            try:
                self._llm_tokenizer = AutoTokenizer.from_pretrained(model_name)
                
                # GPU / 4-bit Logic
                if self.device == "cuda":
                    print("INFO: CUDA detected. Attempting 4-bit load via bitsandbytes...")
                    from transformers import BitsAndBytesConfig
                    
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True,
                    )
                    
                    self._llm_model = AutoModelForCausalLM.from_pretrained(
                        model_name,
                        quantization_config=bnb_config,
                        device_map="auto",
                        low_cpu_mem_usage=True
                    )
                    print("INFO: LLM loaded on CUDA (4-bit).")
                else:
                    print("WARNING: CUDA not found. Loading standard model on CPU (Expect slowness).")
                    self._llm_model = AutoModelForCausalLM.from_pretrained(
                        model_name,
                        torch_dtype=torch.float32,
                        device_map="cpu",
                        low_cpu_mem_usage=True
                    )
                    print("INFO: LLM loaded on CPU.")
                    
            except Exception as e:
                print(f"ERROR: Failed to load LLM: {e}")
                raise e
        
        return self._llm_tokenizer, self._llm_model
