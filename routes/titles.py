import os
from pydantic import BaseModel
from fastapi import APIRouter
from google import genai

router = APIRouter()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


class GenerateRequest(BaseModel):
    title: str
    price: float | None = None
    description: str | None = None
    category: str | None = None


class GenerateResponse(BaseModel):
    new_title: str
    new_description: str


TITLE_SYSTEM_PROMPT = """Tu es un expert en rédaction de titres optimisés SEO pour Etsy et eBay.

Règles :
- Style naturel, pas robotique
- Maximum 80 caractères (très important)
- Inclure les mots-clés importants du produit
- Inclure des mots qui vendent (premium, unique, handmade, etc.)
- Pas de majuscules excessives
- Ne pas dépasser 80 caractères

Réponds uniquement au format JSON suivant (sans markdown, sans code block) :
{
  "title": "ton titre optimisé ici"
}"""


DESCRIPTION_SYSTEM_PROMPT = """Tu es un vendeur e-commerce professionnel avec 10 ans d'expérience.

Règles pour la description :
- Ton professionnel mais chaleureux
- 150-200 mots
- Mentionner les avantages et bénéfices concrets du produit
- Utiliser desacco (oui les gens lisent en diagonale)
- Éviter les formulations génériques type "produit de haute qualité"
- Mentionner le prix s'il est intéressant (bon rapport qualité-prix, pas cher)
- Ne PAS utiliser de emojis dans le texte
- Structure : courte intro, liste des avantages, Call-To-Action à la fin

Réponds uniquement au format JSON suivant (sans markdown, sans code block) :
{
  "description": "ta description optimisée ici"
}"""


@router.post("/")
async def generate_content(data: GenerateRequest):
    base_info = f"Produit à lister :\nTitre original: {data.title}"
    if data.price:
        base_info += f"\nPrix: {data.price}"
    if data.category:
        base_info += f"\nCatégorie: {data.category}"

    # Generate optimized title
    title_prompt = f"""{base_info}

{TITLE_SYSTEM_PROMPT}"""

    title_response = client.models.generate_content(
        model="gemini-2.0-flash-thinking-exp",
        contents=title_prompt,
    )

    # Generate description
    desc_prompt = f"""{base_info}

{DESCRIPTION_SYSTEM_PROMPT}"""

    desc_response = client.models.generate_content(
        model="gemini-2.0-flash-thinking-exp",
        contents=desc_prompt,
    )

    import json

    try:
        new_title = json.loads(title_response.text.strip()).get("title", data.title)
    except Exception:
        new_title = data.title

    try:
        new_description = json.loads(desc_response.text.strip()).get("description", "")
    except Exception:
        new_description = ""

    return GenerateResponse(
        new_title=new_title,
        new_description=new_description,
    )
