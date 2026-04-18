import os
import json
import requests
from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENAI_API_BASE = "https://openrouter.ai/api/v1"
MODEL_NAME = os.environ.get("MODEL_NAME", "openrouter/elephant-alpha")


class GenerateRequest(BaseModel):
    title: str
    price: float | None = None
    description: str | None = None
    category: str | None = None


class GenerateResponse(BaseModel):
    new_title: str
    new_description: str


COMBINED_SYSTEM_PROMPT = """Tu es un expert en e-commerce avec 10 ans d'expérience sur Etsy et eBay.
Tu dois générer un titre optimisé et une description professionnelle pour un produit.

IMPORTANT : 
- Si le titre original est "Homepage", "Sign in", "Enter an address" ou semble être du bruit de l'interface, IGNORE le et demande plus de détails ou utilise la description originale pour comprendre le produit.
- Si tu ne comprends vraiment pas quel est le produit, reponds avec "ERREUR: Produit non détecté sur la page." dans le titre.

Règles pour le TITRE :
- Style naturel, pas robotique, maximum 80 caractères.
- Utilise la description originale pour extraire les vraies caractéristiques Techniques (ex: PC Gamer, CPU, RAM).

Règles pour la DESCRIPTION :
- Ton professionnel mais chaleureux (150-200 mots).
- Garde les faits réels (ne pas inventer de specs techniques).
- Ne PAS utiliser d'emojis.

Réponds UNIQUEMENT au format JSON suivant (sans markdown, sans code block) :
{
  "title": "ton titre optimisé ici",
  "description": "ta description optimisée ici"
}"""


@router.post("/")
async def generate_content(data: GenerateRequest):
    if not OPENROUTER_API_KEY:
        return GenerateResponse(
            new_title=data.title,
            new_description="API key not configured"
        )

    # UI Noise Detection
    noise_keywords = ["homepage", "entrer une adresse", "sign in", "connexion", "mon compte"]
    if any(k in data.title.lower() for k in noise_keywords) and (not data.description or len(data.description) < 20):
        return GenerateResponse(
            new_title="ERREUR: Produit non détecté",
            new_description="Le scraper n'a récupéré que du texte d'interface. Assurez-vous d'être sur une page produit."
        )

    base_info = f"PRODUIT RÉEL À ANALYSER :\nTitre scraper: {data.title}"
    if data.price:
        base_info += f"\nPrix: {data.price}"
    if data.category:
        base_info += f"\nCatégorie: {data.category}"
    if data.description:
        base_info += f"\nDESCRIPTION ORIGINALE DU PRODUIT (utilise ceci comme source de vérité) :\n{data.description[:1500]}"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""{base_info}

{COMBINED_SYSTEM_PROMPT}"""

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000,
    }

    try:
        resp = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        resp_text = resp.json()["choices"][0]["message"]["content"].strip()
        
        # Helper function to clean and parse JSON
        def parse_json_response(text):
            if not text: return {}
            try:
                clean_text = text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                elif clean_text.startswith("```"):
                    clean_text = clean_text.split("```")[1].split("```")[0].strip()
                return json.loads(clean_text)
            except Exception:
                return {}

        result = parse_json_response(resp_text)
        new_title = result.get("title", data.title)
        new_description = result.get("description", "")
        
    except Exception as e:
        print(f"Content generation failed: {e}")
        new_title = data.title
        new_description = f"Error: {str(e)}"

    return GenerateResponse(
        new_title=new_title,
        new_description=new_description,
    )

    return GenerateResponse(
        new_title=new_title,
        new_description=new_description,
    )
