import os
import json
import time
from typing import Dict, Any
from openai import OpenAI

class AIAnalyst:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def analyze(self, ticker: str, question: str, metrics: Dict, forecast: Dict, sec_text: str) -> Dict[str, Any]:
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
            raise ValueError("OpenAI API Key not set.")

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


    def analyze_10k_content(self, ticker: str, html_content: str, focus: str = "overview", max_chars: int = 60000) -> Dict[str, Any]:
        """
        Analyzes raw 10-K HTML content.
        returns: Dict with keys matching the requested JSON schema.
        """
        # 1. Clean HTML
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "lxml")
            for script in soup(["script", "style"]):
                script.extract()
            text_content = soup.get_text(separator="\n")
            # Normalize whitespace
            lines = (line.strip() for line in text_content.splitlines())
            text_content = '\n'.join(chunk for chunk in lines if chunk)
        except Exception as e:
            text_content = html_content # Fallback to raw if soup fails?
            print(f"HTML parsing failed: {e}")

        # 2. Truncate
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "...[TRUNCATED]"

        # 3. Construct Prompt
        # Simplified for robustness
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
        
        user_prompt = f"""
        Ticker: {ticker}
        Focus: {focus}
        
        10-K Text (excerpt):
        {text_content}
        """

        fallback_result = {
            "executive_summary": "AI Analysis Unavailable (Quota exceeded or Key missing).",
            "key_points": [],
            "risks": [],
            "financial_drivers": [],
            "what_to_watch": []
        }

        if not self.client:
             return fallback_result

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
            # Clean possible markdown
            if content.startswith("```json"): content = content[7:]
            if content.endswith("```"): content = content[:-3]
            return json.loads(content.strip())

        except Exception as e:
            print(f"10-K AI Analysis Failed: {e}")
            return fallback_result
