from typing import Protocol

from pydantic import BaseModel, Field

PROMPT = """Tu lis le texte d'une facture française et tu remplis les champs demandés.
Règles :
- Recopie les valeurs telles qu'elles figurent sur la facture, n'invente rien.
- Si une valeur est absente ou illisible, mets null.
- Les montants sont des nombres avec un point décimal, sans symbole (1234.50).
- La date est celle d'émission de la facture, au format AAAA-MM-JJ.
- supplier est l'entreprise qui émet la facture, pas le client.
- currency est le code ISO à 3 lettres (EUR par défaut si le symbole € apparaît).

Texte de la facture :
"""


class ExtractedInvoice(BaseModel):
    supplier: str | None = Field(default=None, description="Nom du fournisseur")
    invoice_number: str | None = Field(default=None, description="Numéro de facture")
    invoice_date: str | None = Field(default=None, description="Date AAAA-MM-JJ")
    amount_excl_tax: float | None = Field(default=None, description="Total HT")
    vat_amount: float | None = Field(default=None, description="Total TVA")
    amount_incl_tax: float | None = Field(default=None, description="Total TTC")
    currency: str | None = Field(default=None, description="Code devise ISO")


class ExtractionError(Exception):
    pass


class InvoiceExtractor(Protocol):
    def extract(self, text: str) -> ExtractedInvoice: ...


class GeminiExtractor:
    def __init__(self, api_key: str | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def extract(self, text: str) -> ExtractedInvoice:
        if not self.api_key:
            raise ExtractionError("Clé GEMINI_API_KEY manquante dans .env")

        from google import genai
        from google.genai import errors, types

        client = genai.Client(api_key=self.api_key)
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=PROMPT + text,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedInvoice,
                    temperature=0,
                ),
            )
        except errors.APIError as e:
            raise ExtractionError(f"Erreur de l'API Gemini : {e.message}") from e

        if not isinstance(response.parsed, ExtractedInvoice):
            raise ExtractionError("Réponse de Gemini illisible")
        return response.parsed
