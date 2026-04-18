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


TITLE_SYSTEM_PROMPT = """Tu es un expert en redaction de titres optimises SEO pour Etsy et eBay.

Regles :
- Style naturel, pas robotique
- Maximum 80 caracteres (tres important)
- Inclure les mots-cles importants du produit
- Inclure des mots qui vendent (premium, unique, handmade, etc.)
- Pas de majuscules excessives
- Ne pas depasser 80 caracteres

Reponds uniquement au format JSON suivant (sans markdown, sans code block) :
{
  "title": "ton titre optimise ici"
}"""


DESCRIPTION_SYSTEM_PROMPT = """Tu es un vendeur e-commerce professionnel avec 10 ans d'experience.

Regles pour la description :
- Ton professionnel mais chaleureux
- 150-200 mots
- Mentionner les avantages et benefices concrets du produit
- Utiliser desacco (oui les gens lisent en diagonale)
- Eviter les formulations generiques type "produit de haute qualite"
- Mentionner le prix s'il est interessant (bon rapport qualite-prix, pas cher)
- Ne PAS utiliser de emojis dans le texte
- Structure : courte intro, liste des avantages, Call-To-Action a la fin

Reponds uniquement au format JSON suivant (sans markdown, sans code block) :
{
  "description": "ta description optimisée ici"
}"""


@router.post("/")
async def generate_content(data: GenerateRequest):
    if not OPENROUTER_API_KEY:
        return GenerateResponse(
            new_title=data.title,
            new_description="API key not configured"
        )

    base_info = f"Produit a lister :\nTitre original: {data.title}"
    if data.price:
        base_info += f"\nPrix: {data.price}"
    if data.category:
        base_info += f"\nCategorie: {data.category}"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # Generate optimized title
    title_prompt = f"""{base_info}

{TITLE_SYSTEM_PROMPT}"""

    title_payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": title_prompt}],
        "temperature": 0.7,
        "max_tokens": 256,
    }

    try:
        title_resp = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=title_payload,
            timeout=30,
        )
        title_resp.raise_for_status()
        title_text = title_resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Title generation failed: {e}")
        title_text = ""

    # Generate description
    desc_prompt = f"""{base_info}

{DESCRIPTION_SYSTEM_PROMPT}"""

    desc_payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": desc_prompt}],
        "temperature": 0.7,
        "max_tokens": 512,
    }

    try:
        desc_resp = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=desc_payload,
            timeout=30,
        )
        desc_resp.raise_for_status()
        desc_text = desc_resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Description generation failed: {e}")
        desc_text = ""

    # Helper function to clean and parse JSON
    def parse_json_response(text, fallback_key=None, fallback_value=None):
        if not text:
            return fallback_value
        try:
            # Remove possible markdown formatting
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text.split("```json")[1].split("```")[0].strip()
            elif clean_text.startswith("```"):
                clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(clean_text)
            if fallback_key:
                return data.get(fallback_key, fallback_value)
            return data
        except Exception:
            return fallback_value

    new_title = parse_json_response(title_text, "title", data.title)
    new_description = parse_json_response(desc_text, "description", "")

    return GenerateResponse(
        new_title=new_title,
        new_description=new_description,
    )
