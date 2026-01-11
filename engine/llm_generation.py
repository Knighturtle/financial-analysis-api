
import json
import torch
import os
import requests
from typing import Dict, Any, List
from engine.models import ModelManager

def generate_with_ollama(prompt: str, model: str = None) -> str:
    """
    Generates text using Ollama API.
    Selects model based on LLM_PROFILE if model is not provided.
    """
    url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    
    if not model:
        profile = os.getenv("LLM_PROFILE", "finance").lower()
        if profile == "finance":
            model = os.getenv("OLLAMA_MODEL_FINANCE", "qwen2.5:7b")
        else:
            model = os.getenv("OLLAMA_MODEL_GENERAL", "llama3.1:8b")
            
    print(f"INFO: Calling Ollama with model={model}...")
    
    endpoint = f"{url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=300)
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.RequestException as e:
        print(f"ERROR: Ollama Request Failed: {e}")
        raise Exception(f"Ollama API Error: {str(e)}")

class LLMReporter:
    def __init__(self):
        self.model_manager = ModelManager()

    def generate_report(self, ticker: str, finbert_risks: List[Dict], md_a_text: str, full_html_text: str) -> Dict[str, Any]:
        """
        Generates analysis report using local LLM with compressed context.
        """
        try:
            tokenizer, model = self.model_manager.get_llm()
        except Exception as e:
            return {
                "provider": "huggingface_local", 
                "used": False, 
                "error": f"Model Load Failed: {str(e)}"
            }

        # 1. Context Construction (Compression)
        # Strategy: 
        # - Top 15 FinBERT risks (High value) -> ~500 chars
        # - MD&A Excerpt (High value) -> ~2000 chars
        # - General 10-K Excerpt (Fallback) -> ~2000 chars
        
        # Risk Text
        risk_str = "No specific high-risk sentences detected."
        if finbert_risks:
            risk_lines = [f"- {r['text']} (Score: {r['score']:.2f})" for r in finbert_risks[:15]]
            risk_str = "\n".join(risk_lines)
            
        # MD&A / Text
        # If we have explicit MD&A, use it. Otherwise use truncated full text.
        context_text = md_a_text[:3000] if md_a_text else full_html_text[:3000]
        
        system_prompt = (
            "You are a senior financial analyst. "
            "Analyze the provided 10-K data (Risks & MD&A). "
            "Output ONLY valid JSON. "
            "Keys: executive_summary, key_points, risks, financial_drivers, what_to_watch."
        )
        
        user_prompt = f"""
        Ticker: {ticker}
        
        [Top Verified Risks (AI Scored)]
        {risk_str}
        
        [Financial Condition (MD&A/Excerpt)]
        {context_text}
        
        Generate a strict JSON financial analysis.
        """
        
        # Format prompt
        messages = [
            {"role": "user", "content": system_prompt + "\n\n" + user_prompt}
        ]
        
        # Generation Params from Env
        max_tokens = int(os.getenv("HF_MAX_NEW_TOKENS", "800"))
        temperature = 0.3 # stable

        try:
            # Tokenize
            if hasattr(tokenizer, "apply_chat_template"):
                input_ids = tokenizer.apply_chat_template(messages, return_tensors="pt").to(model.device)
            else:
                 # Fallback
                 text_input = f"{system_prompt}\n\n{user_prompt}\n\nJSON Output:"
                 input_ids = tokenizer(text_input, return_tensors="pt").input_ids.to(model.device)

            outputs = model.generate(
                input_ids, 
                max_new_tokens=max_tokens, 
                do_sample=True, 
                temperature=temperature,
                pad_token_id=tokenizer.eos_token_id
            )
            generated_text = tokenizer.decode(outputs[0][len(input_ids[0]):], skip_special_tokens=True)
            
            return self._parse_json(generated_text)
            
        except Exception as e:
            return {
                "provider": "huggingface_local",
                "used": False,
                "error": f"Generation Failed: {str(e)}"
            }

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        Attempts to parse JSON from LLM output.
        """
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = text[start:end]
                data = json.loads(json_str)
                return {
                    "provider": "huggingface_local",
                    "used": True,
                    "analysis": data
                }
        except:
            pass
            
        return {
            "provider": "huggingface_local",
            "used": True,
            "error": "JSON Parsing Failed",
            "raw_output": text[:500]
        }
