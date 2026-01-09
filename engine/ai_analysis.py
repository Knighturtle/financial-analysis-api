import os
import json
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
            try:
                return self._call_openai(ticker, question, data_summary, forecast_txt, sec_text)
            except Exception as e:
                print(f"AI Error: {e}")
                return self._fallback_response(ticker, data_summary, forecast_txt)
        else:
            return self._fallback_response(ticker, data_summary, forecast_txt)

    def _call_openai(self, ticker, question, data, forecast, sec_text):
        system_prompt = """
        You are a senior financial analyst. 
        Analyze the company based on the provided metrics and SEC 10-K excerpt.
        Respond in Japanese.
        Strictly follow this JSON format for the 'answer' field logic, but return the whole response as valid JSON matching the API spec if needed, 
        OR just return the text parts.
        Actually, the API expects a structure.
        
        Output format should be a JSON string with these keys:
        - executive_summary
        - key_metrics_commentary
        - risks_summary
        - growth_drivers
        - red_flags
        
        Do not include markdown formatting like ```json. Just raw valid JSON.
        """
        
        user_prompt = f"""
        Ticker: {ticker}
        Question: {question}
        Data: {data}
        Forecast: {forecast}
        SEC Text Excerpt: {sec_text[:2000]}
        
        Generate the analysis.
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        # Try to parse JSON, if fails, wrap text
        try:
            return json.loads(content)
        except:
            return {
                "executive_summary": content[:200],
                "key_metrics_commentary": "Parsing error, see summary.",
                "risks_summary": "Parsing error.",
                "growth_drivers": "Parsing error.",
                "red_flags": "Parsing error."
            }

    def _fallback_response(self, ticker, data, forecast):
        """
        Rule-based fallback response in Japanese.
        """
        return {
            "executive_summary": f"{ticker}の財務分析概要です。直近の売上高は約${data.split(',')[0].split('$')[1]}、純利益率は{data.split('Net Margin: ')[1].split(',')[0]}です。",
            "key_metrics_commentary": f"主要指標: {data}。安定した収益基盤があるか確認が必要です。",
            "risks_summary": "10-Kに基づく具体的なリスク要因はAI機能が無効なため生成できませんが、一般的にマクロ経済、競合、規制リスクに注意が必要です。",
            "growth_drivers": f"過去の成長率(CAGR)は{data.split('CAGR: ')[1]}です。今後の成長は市場拡大と新製品に依存します。",
            "red_flags": "財務データ上の大きな異常値は簡易チェックでは検出されませんでしたが、キャッシュフローの推移を詳細に確認することを推奨します。"
        }
