import os
import json
import requests
from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-thinking-exp:generateContent"


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


SYSTEM_PROMPT = """Tu es un expert en analyse de produits e-commerce. Tu dois évaluer si un produit est un "winning product" sur une échelle de 0 à 100.

Critères de scoring (25 points chacun) :
1. Popularité actuelle (trending) - le produit est-il en train de gagner en popularité ?
2. Nouveau listing (listed récemment) - a-t-il été listé récemment (moins de 6 mois) ?
3. Bonnes reviews (note + nombre) - note >= 4.0 ET >= 50 reviews =满分
4. Preuves de ventes (sales, orders count) - nombre de ventes visible

Réponds STRICTEMENT au format JSON suivant (sans markdown, sans code block) :
{
  "score": [0-100],
  "explanation": "courte explication de 1-2 phrases",
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

    # Optionally enhance with AI if API key is available
    if os.environ.get("GEMINI_API_KEY"):
        try:
            prompt = f"""Analyse ce produit e-commerce :

Titre: {data.title}
Prix: {data.price}
Reviews: {data.reviews}
Note: {data.rating}
Ventes: {data.sales}
Date de listing: {data.listing_date}
Catégorie: {data.category}

{SYSTEM_PROMPT}"""

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512},
            }
            resp = requests.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            ai_result = json.loads(
                resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            )
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
