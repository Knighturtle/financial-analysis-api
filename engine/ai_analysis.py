import os
import json
import time
from typing import Dict, Any
from openai import OpenAI

class AIAnalyst:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def analyze(self, ticker: str, question: str, metrics: Dict, forecast: Dict, sec_text: str, output_lang: str = None) -> Dict[str, Any]:
        """
        Generates analysis text.
        If API key exists: Calls OpenAI.
        If no API key (or failure): Returns rule-based template.
        """
        
        # Prepare Data Summary for Prompt/Template
        rev = metrics.get('revenue', 0) / 1e9 # Billions
        margin = metrics.get('net_margin', 0) * 100
        cagr = metrics.get('revenue_cagr_3yr', 0) * 100
        
        data_summary = (
            f"Revenue: ${rev:.2f}B, "
            f"Net Margin: {margin:.1f}%, "
            f"3Y CAGR: {cagr:.1f}%"
        )
        
        forecast_txt = "Not available"
        if forecast:
            next_rev = forecast['forecast_revenue'][0] / 1e9
            forecast_txt = f"Next Year Projected Revenue: ${next_rev:.2f}B"

        if os.getenv("OLLAMA_URL"):
            # Use Ollama
            try:
                return self._call_ollama(ticker, question, data_summary, forecast_txt, sec_text, output_lang)
            except Exception as e:
                # Decide if fallback to OpenAI or fail? 
                # User says "Implement Ollama", so if it fails, maybe fail or fallback.
                # Let's log and try OpenAI if key exists, else raise.
                print(f"Ollama Failed: {e}. Falling back to OpenAI if available.")
                if not (self.client and self.api_key):
                     raise ValueError(f"Ollama failed and OpenAI Key not set: {e}")

        if self.client and self.api_key:
            max_retries = 3
            backoff = 1
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    result = self._call_openai(ticker, question, data_summary, forecast_txt, sec_text)
                    # Simple validation: checks if we got meaningful keys
                    if result and result.get("executive_summary") and len(result["executive_summary"]) > 20:
                        return result
                    else:
                        print(f"AI Response validation failed (Attempt {attempt+1}). Retrying...")
                        time.sleep(backoff)
                        backoff *= 2
                except Exception as e:
                    print(f"AI Error (Attempt {attempt+1}): {e}")
                    last_error = e
                    time.sleep(backoff)
                    backoff *= 2
            
            # If we get here, all retries failed
            raise ValueError(f"AI Analysis failed after {max_retries} attempts: {last_error or 'Invalid response'}")
        else:
             # Should not happen if api/main.py checks, but strict error here too
            raise ValueError("OpenAI API Key not set and Ollama not configured.")

    def _call_ollama(self, ticker, question, data, forecast, sec_text, output_lang: str = None):
        from engine.llm_generation import generate_with_ollama
        
        # Priority: explicit arg > env var > default 'ja'
        lang = (output_lang or os.getenv("OUTPUT_LANG", "ja")).lower()
        is_english = lang == "en"
        
        # Define Language Specific Instructions
        if is_english:
            role_desc = "You are a professional financial analyst."
            instructions = """
            - Output strictly in **English**.
            - Provide a comprehensive analysis based on the data.
            - Format the response as a valid **JSON string** only. No markdown formatting.
            - Use the EXACT structure below.
            """
            section_desc = """
            1. Executive Summary
            2. Key Metrics Analysis (Strengths/Weaknesses)
            3. Risks Summary
            4. Future Action/Growth Drivers
            5. Red Flags
            """
        else:
            role_desc = "あなたはプロの財務アナリストです。"
            instructions = """
            - **日本語**で出力してください。
            - データに基づいた包括的な分析を提供してください。
            - 回答は **純粋なJSON文字列** のみで出力してください。Markdown装飾は不要です。
            - 以下の構造を厳守してください。
            """
            section_desc = """
            1. エグゼクティブサマリー (要約)
            2. 主要指標の分析 (強み・弱み)
            3. リスク要因
            4. 今後のアクション提案 / 成長要因
            5. 懸念点 (Red Flags)
            """

        prompt = f"""
        {role_desc}
        Target: {ticker}
        Question: {question}

        [Financial Data]
        {data}

        [Forecast]
        {forecast}

        [Instructions]
        {instructions}
        
        [Required JSON Structure]
        {{
            "executive_summary": "...",
            "key_metrics_commentary": "...",
            "risks_summary": "...",
            "growth_drivers": "...",
            "red_flags": "..."
        }}
        
        Do not output any conversational text, only the JSON.
        """

        try:
            # Call Ollama (Model determined by Env Profile in llm_generation)
            raw_response = generate_with_ollama(prompt)
            
            # Clean
            clean_resp = raw_response.strip()
            if clean_resp.startswith("```json"): clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"): clean_resp = clean_resp[:-3]
            
            return json.loads(clean_resp.strip())
        except Exception as e:
            print(f"Ollama JSON parse failed or error: {e}")
            return {
                "executive_summary": f"Ollama Parsing Error ({lang}): {str(e)}",
                "key_metrics_commentary": "N/A",
                "risks_summary": "N/A",
                "growth_drivers": "N/A",
                "red_flags": "N/A"
            }

    def _call_openai(self, ticker, question, data, forecast, sec_text):
        system_prompt = """
        あなたは熟練した財務アナリストです。
        提供された財務指標とSECの10-K抜粋に基づいて、企業の分析を行ってください。
        
        【重要】
        - **日本語**で回答してください。
        - 以下のJSONフォーマットを厳守してください。
        - **Markdown形式（```jsonなど）は絶対に含めないでください。** 純粋なJSON文字列のみを返してください。
        
        {
            "executive_summary": "全体的な評価と要約（200文字程度）",
            "key_metrics_commentary": "主要な財務指標に基づいた分析（収益性、成長性など）",
            "risks_summary": "SEC抜粋や財務状況から読み取れるリスク要因",
            "growth_drivers": "今後の成長を牽引する要素",
            "red_flags": "懸念点や注意すべき兆候（なければ'特になし'）"
        }
        """
        
        # Handle case where sec_text is short or empty
        sec_context = sec_text[:4000] if sec_text and len(sec_text) > 100 else "SEC詳細情報なし（財務数値のみで分析してください）"
        
        user_prompt = f"""
        対象企業: {ticker}
        質問: {question}
        
        【財務データ】
        {data}
        
        【予測値】
        {forecast}
        
        【SEC 10-K 抜粋】
        {sec_context}
        
        上記情報を統合し、客観的かつ洞察に富んだ分析を作成してください。
        """
        
        try:
            # Enforcing 30s timeout per call
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                timeout=30.0 
            )
            
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            return json.loads(content)
            
        except json.JSONDecodeError:
            print(f"JSON Parse Error. Content: {content[:100]}...")
            return {
                "executive_summary": "分析は生成されましたが、フォーマット変換に失敗しました。",
                "key_metrics_commentary": content[:300] + "...", 
                "risks_summary": "フォーマットエラー",
                "growth_drivers": "フォーマットエラー",
                "red_flags": "フォーマットエラー"
            }
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            raise e # Raise to allow upstream handling (api/main.py)


    async def analyze_10k_content(self, ticker: str, html_content: str, focus: str = "overview", 
                                  max_chars: int = 60000, 
                                  use_finbert: bool = False, 
                                  use_llm: bool = False,
                                  finbert_top_n: int = 15) -> Dict[str, Any]:
        """
        Analyzes raw 10-K HTML content.
        Supports OpenAI, FinBERT, and Local LLM.
        """
        result_agg = {}

        # 1. Clean HTML
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "lxml")
            for script in soup(["script", "style"]):
                script.extract()
            text_content = soup.get_text(separator="\n")
            lines = (line.strip() for line in text_content.splitlines())
            text_content = '\n'.join(chunk for chunk in lines if chunk)
        except Exception as e:
            text_content = html_content 
            print(f"HTML parsing failed: {e}")

        # 2. FinBERT Analysis
        if use_finbert:
            try:
                from engine.risk_analysis import RiskAnalyst
                risk_analyst = RiskAnalyst()
                # Run sync for now, or could threadpool it if heavy blocking
                finbert_res = risk_analyst.analyze_risk(html_content, top_n=finbert_top_n)
                result_agg["finbert"] = finbert_res
            except Exception as e:
                result_agg["finbert"] = {"error": str(e)}

        # 3. LLM Analysis (Local) or OpenAI
        # If use_llm is True, we use Local LLM INSTEAD or ALONG WITH OpenAI?
        # Requirement: "Financial LLM... Financial LLM analysis (generative)"
        # If use_llm is True (local), we do that.
        # If use_ai is True (from caller) and NO local requested, we use OpenAI.
        
        # We will separate the logic:
        # If use_llm=True -> Run Local LLM
        # If use_llm=False -> Run OpenAI (if client available) - essentially preserving old behavior 
        # But wait, the request body has `use_ai`. 
        
        analysis_data = {
            "executive_summary": "Analysis not performed.",
            "key_points": [], "risks": [], "financial_drivers": [], "what_to_watch": []
        }

        if use_llm:
            try:
                from engine.llm_generation import LLMReporter
                llm_reporter = LLMReporter()
                
                # Context Prep
                finbert_risks = result_agg.get("finbert", {}).get("top_risk_sentences", [])
                
                # Try simple MD&A extraction (Item 7) similar to Risk extraction
                # For now, we reuse the text_content or write a quick extractor
                # We'll just pass the full text_content as "full_html_text" 
                # and let llm_reporter truncate it if md_a isn't separate, 
                # OR we implement MD&A extraction here.
                # Let's do a simple regex for Item 7 here for better quality
                import re
                md_a_text = ""
                try:
                    # Very rough heuristic for Item 7
                    start = re.search(r"Item\s*7\.?", text_content, re.IGNORECASE)
                    end = re.search(r"Item\s*8\.?", text_content, re.IGNORECASE)
                    if start and end:
                        md_a_text = text_content[start.end():end.start()]
                except:
                    pass

                llm_res = llm_reporter.generate_report(
                    ticker=ticker, 
                    finbert_risks=finbert_risks, 
                    md_a_text=md_a_text, 
                    full_html_text=text_content
                )
                
                if llm_res.get("used"):
                    # map local llm analysis to main analysis keys if strictly json
                    if "analysis" in llm_res:
                        analysis_data = llm_res["analysis"]
                
                result_agg["llm"] = llm_res
                # Populate main analysis fields for UI compatibility
                if llm_res.get("used") and "analysis" in llm_res:
                    analysis_data = llm_res["analysis"]

            except Exception as e:
                result_agg["llm"] = {"error": str(e)}

        # Fallback to OpenAI if Local LLM not used/failed AND we want AI
        # However, checking if "Local LLM" was requested.
        elif self.client and self.api_key:
            # Existing OpenAI Logic
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars] + "...[TRUNCATED]"

            system_prompt = """
            You are a financial analyst. Analyze the provided SEC 10-K text.
            Return ONLY valid JSON. No Markdown.
            JSON format:
            {
                 "executive_summary": "Summary (200 chars)",
                 "key_points": ["bullet 1", "bullet 2"],
                 "risks": ["risk 1", "risk 2"],
                 "financial_drivers": ["driver 1", "driver 2"],
                 "what_to_watch": ["item 1", "item 2"]
            }
            """
            user_prompt = f"Ticker: {ticker}\nFocus: {focus}\n10-K Text (excerpt):\n{text_content}"
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    timeout=45.0
                )
                content = response.choices[0].message.content.strip()
                if content.startswith("```json"): content = content[7:]
                if content.endswith("```"): content = content[:-3]
                analysis_data = json.loads(content.strip())
            except Exception as e:
                print(f"OpenAI 10-K Analysis Failed: {e}")
        
        # Merge Results
        # If we computed finbert but not LLM, we still want to return a dict that works for UI
        # The UI expects 'analysis' key at root level usually or we modify API response.
        
        # If Local LLM was used, analysis_data is populated from it.
        # If OpenAI was used, analysis_data is populated from it.
        # If neither, it's empty/dummy.
        
        result_agg.update(analysis_data)
        return result_agg
