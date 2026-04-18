import os
import json
import requests
from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENAI_API_BASE = "https://openrouter.ai/api/v1"
MODEL_NAME = os.environ.get("MODEL_NAME", "openrouter/elephant-alpha")


class AnalyzeRequest(BaseModel):
    title: str
    price: float | None = None
    reviews: int | None = None
    rating: float | None = None
    sales: int | None = None
    listing_date: str | None = None
    category: str | None = None


class AnalyzeResponse(BaseModel):
    score: int
    explanation: str
    breakdown: dict


SYSTEM_PROMPT = """Tu es un expert en analyse de produits e-commerce. Tu dois évaluer si un produit est un "winning product" (à fort potentiel de vente) sur une échelle de 0 à 100.

IMPORTANT : 
- Si certaines données sont manquantes (null), base ton analyse sur les informations disponibles (Titre, Catégorie).
- Le score doit refléter le POTENTIEL du produit. Un produit avec peu de données mais un titre très "viral" ou "tendance" peut quand même avoir un score correct (> 50).
- Ne sois pas trop pessimiste. Si tu reconnais un type de produit qui se vend bien (ex: bijoux personnalisés, gadgets tech utiles), donne un score généreux même sans preuve de ventes immédiate.

Critères de scoring (25 points chacun) :
1. Popularité/Tendance - le type de produit est-il recherché ?
2. Récence - est-ce une nouveauté ou un classique indémodable ?
3. Preuve sociale - qualité perçue via le titre et les reviews (si présentes).
4. Potentiel de vente - attractivité globale.

Réponds STRICTEMENT au format JSON suivant (sans markdown, sans code block) :
{
  "score": [0-100],
  "explanation": "courte explication de 1-2 phrases positive et encourageante",
  "breakdown": {
    "popularity": [0-25],
    "recency": [0-25],
    "reviews": [0-25],
    "sales": [0-25]
  }
}"""


def calculate_recency_score(listing_date: str | None) -> tuple[int, str]:
    """Calculate recency score based on listing date."""
    if not listing_date:
        return 10, "Date de listing non disponible"

    try:
        from datetime import datetime
        listing_dt = datetime.fromisoformat(listing_date.replace("Z", "+00:00"))
        now = datetime.now(listing_dt.tzinfo)
        days_old = (now - listing_dt).days

        if days_old < 30:
            return 25, f"Produit très récent ({days_old} jours)"
        elif days_old < 90:
            return 20, f"Produit récent ({days_old} jours)"
        elif days_old < 180:
            return 12, f"Produit modérément récent ({days_old} jours)"
        elif days_old < 365:
            return 5, f"Produit ancien ({days_old} jours)"
        else:
            return 0, f"Produit très ancien ({days_old} jours)"
    except Exception:
        return 10, "Date de listing non analysable"


def calculate_reviews_score(rating: float | None, reviews: int | None) -> tuple[int, str]:
    """Calculate reviews score based on rating and review count."""
    if not rating and not reviews:
        return 10, "Pas de données reviews"

    score = 0
    reasons = []

    if rating:
        if rating >= 4.5:
            score += 15
            reasons.append(f"Note excellente: {rating}/5")
        elif rating >= 4.0:
            score += 10
            reasons.append(f"Bonne note: {rating}/5")
        elif rating >= 3.0:
            score += 5
            reasons.append(f"Note moyenne: {rating}/5")
        else:
            reasons.append(f"Note faible: {rating}/5")

    if reviews:
        if reviews >= 500:
            score += 10
            reasons.append(f"{reviews} reviews (très populaire)")
        elif reviews >= 100:
            score += 8
            reasons.append(f"{reviews} reviews (populaire)")
        elif reviews >= 50:
            score += 5
            reasons.append(f"{reviews} reviews (correct)")
        else:
            score += 2
            reasons.append(f"{reviews} reviews (peu de reviews)")

    return min(score, 25), ", ".join(reasons) if reasons else "Reviews insuffisants"


def calculate_sales_score(sales: int | None) -> tuple[int, str]:
    """Calculate sales proof score."""
    if not sales:
        return 8, "Nombre de ventes non visible (peut être un bon signe ou mauvais)"

    if sales >= 1000:
        return 25, f"{sales}+ ventes (best-seller)"
    elif sales >= 500:
        return 22, f"{sales} ventes (très populaire)"
    elif sales >= 100:
        return 17, f"{sales} ventes (populaire)"
    elif sales >= 50:
        return 12, f"{sales} ventes (correct)"
    else:
        return 6, f"{sales} ventes (début de traction)"


def calculate_popularity_score(title: str, category: str | None) -> tuple[int, str]:
    """Calculate popularity/trending score based on product signals."""
    title_lower = title.lower()

    trending_keywords = [
        "trending", "viral", "best seller", "bestseller", "popular",
        "top", "most wanted", "must have", "hit", "sensation",
        "new arrival", "new release", "limited", "exclusive"
    ]

    category_trending = [
        "toys", "games", "electronics", "fitness", "wellness",
        "home decor", "kitchen", "outdoor", "fashion accessories"
    ]

    score = 12  # Base score

    for keyword in trending_keywords:
        if keyword in title_lower:
            score += 3
            break

    if category:
        for cat in category_trending:
            if cat in category.lower():
                score += 5
                break

    return min(score, 25), f"Score Popularité: {score}/25"


@router.post("/")
async def analyze_product(data: AnalyzeRequest):
    # Calculate individual scores
    popularity_score, popularity_reason = calculate_popularity_score(data.title, data.category)
    recency_score, recency_reason = calculate_recency_score(data.listing_date)
    reviews_score, reviews_reason = calculate_reviews_score(data.rating, data.reviews)
    sales_score, sales_reason = calculate_sales_score(data.sales)

    total_score = popularity_score + recency_score + reviews_score + sales_score

    breakdown = {
        "popularity": popularity_score,
        "recency": recency_score,
        "reviews": reviews_score,
        "sales": sales_score,
    }

    explanations = [
        popularity_reason,
        recency_reason,
        reviews_reason,
        sales_reason,
    ]

    explanation = f"Score global: {total_score}/100. " + ". ".join(explanations)

    # Optionally enhance with AI if OpenRouter is configured
    if OPENROUTER_API_KEY:
        try:
            prompt = f"""Analyse ce produit e-commerce :
    
Titres: {data.title}
Prix: {data.price}
Reviews: {data.reviews}
Note: {data.rating}
Ventes: {data.sales}
Date de listing: {data.listing_date}
Catégorie: {data.category}

{SYSTEM_PROMPT}"""

            payload = {
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 512,
            }
            resp = requests.post(
                f"{OPENAI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            ai_text = resp.json()["choices"][0]["message"]["content"].strip()
            
            # Remove possible markdown formatting from model response
            if ai_text.startswith("```json"):
                ai_text = ai_text.split("```json")[1].split("```")[0].strip()
            elif ai_text.startswith("```"):
                ai_text = ai_text.split("```")[1].split("```")[0].strip()
                
            ai_result = json.loads(ai_text)
            total_score = ai_result.get("score", total_score)
            explanation = ai_result.get("explanation", explanation)
            breakdown = ai_result.get("breakdown", breakdown)
        except Exception as e:
            print(f"AI enhancement failed: {e}")

    return AnalyzeResponse(
        score=total_score,
        explanation=explanation,
        breakdown=breakdown,
    )
