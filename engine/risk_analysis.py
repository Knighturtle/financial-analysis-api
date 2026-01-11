
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from engine.models import ModelManager

class RiskAnalyst:
    def __init__(self):
        self.model_manager = ModelManager()

    def _extract_risk_section(self, html_content: str) -> str:
        """
        Attempts to extract Item 1A. Risk Factors.
        Simple heuristic: Find "Item 1A" and "Item 1B" (or "Item 2") and take text between.
        Falls back to full text if not found.
        """
        soup = BeautifulSoup(html_content, "lxml")
        text = soup.get_text(separator="\n")
        
        # Regex for Item 1A header
        # Matches "Item 1A." possibly followed by "Risk Factors" case insensitive
        # allowing for some whitespace
        start_pattern = re.compile(r"Item\s*1A\.?\s*Risk\s*Factors", re.IGNORECASE)
        # End pattern: Item 1B or Item 2
        end_pattern = re.compile(r"Item\s*(1B|2)\.?", re.IGNORECASE)
        
        start_match = start_pattern.search(text)
        if start_match:
            start_idx = start_match.start()
            end_match = end_pattern.search(text, start_idx)
            if end_match:
                end_idx = end_match.start()
                return text[start_idx:end_idx]
            else:
                # Take next 50000 chars if end not found
                return text[start_idx:start_idx+50000]
        
        return text[:50000] # Fallback to first 50k chars of doc if section not found

    def _split_sentences(self, text: str) -> List[str]:
        # Simple splitting by period, roughly. 
        # For better results, NLTK would be good but staying lightweight with regex
        # Cleaning extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Split by .!? followed by space or end
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s) > 20] # Filter very short fragments

    def analyze_risk(self, html_content: str, top_n: int = 15) -> Dict[str, Any]:
        """
        Extracts risk section, runs FinBERT, returns top risky sentences.
        """
        try:
            finbert = self.model_manager.get_finbert()
        except Exception as e:
            return {"error": f"FinBERT Model Load Failed: {str(e)}", "top_risk_sentences": []}

        risk_text = self._extract_risk_section(html_content)
        sentences = self._split_sentences(risk_text)
        
        # Limit total sentences to process to avoid massive wait on CPU (e.g. max 200)
        # Prioritize first 200 sentences of Risk Factors
        sentences = sentences[:200]
        
        if not sentences:
             return {
                "model": "ProsusAI/finbert",
                "top_risk_sentences": [],
                "summary_stats": {"negative": 0, "neutral": 0, "positive": 0}
            }

        # Batch inference? Pipeline handles lists efficiently usually
        try:
            results = finbert(sentences) # List of lists of scores
        except Exception as e:
             return {"error": f"Inference Failed: {str(e)}", "top_risk_sentences": []}
            
        # Structure: results = [[{'label': 'positive', 'score': 0.1}, ...], ...] depending on return_all_scores=True
        
        scored_sentences = []
        neg_count = 0
        neu_count = 0
        pos_count = 0

        for sent, scores in zip(sentences, results):
            # scores is a list of dicts: [{'label': 'positive', 'score': X}, ...]
            # Find negative score
            neg_score = 0
            predicted_label = "neutral"
            highest_score = 0
            
            for item in scores:
                if item['score'] > highest_score:
                    highest_score = item['score']
                    predicted_label = item['label']
                
                if item['label'] == 'negative':
                    neg_score = item['score']
            
            if predicted_label == 'negative': neg_count += 1
            elif predicted_label == 'positive': pos_count += 1
            else: neu_count += 1

            scored_sentences.append({
                "text": sent,
                "label": predicted_label,
                "score": float(neg_score) # We sort by negative score primarily
            })

        # Sort by negative score descending
        scored_sentences.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            "model": "ProsusAI/finbert",
            "top_risk_sentences": scored_sentences[:top_n],
            "summary_stats": {
                "negative": neg_count,
                "neutral": neu_count,
                "positive": pos_count,
                "total_sentences_analyzed": len(sentences)
            }
        }
