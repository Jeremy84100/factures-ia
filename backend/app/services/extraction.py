from typing import Protocol

from pydantic import BaseModel, Field

PROMPT = """Tu es un assistant comptable. Tu reçois une facture en PDF et le texte qu'un OCR en a tiré.
Le PDF fait foi : regarde aussi le logo, l'en-tête et la mise en page. Le texte t'aide à lire les chiffres.
Règles :
- Recopie les valeurs telles qu'elles figurent sur la facture. N'invente jamais rien : si une valeur est absente ou illisible, mets null.
- Les montants sont des nombres avec un point décimal, sans symbole (1234.50). Un avoir a des montants négatifs.

Texte OCR de la facture :
"""


class ExtractedInvoice(BaseModel):
    supplier: str | None = Field(
        default=None,
        description="Raison sociale de l'entreprise qui émet la facture, souvent dans le logo ou l'en-tête. Jamais le client, jamais une personne de contact.",
    )
    invoice_number: str | None = Field(
        default=None, description="Numéro de la facture ou de l'avoir"
    )
    invoice_date_raw: str | None = Field(
        default=None,
        description="Date d'émission recopiée exactement comme elle est écrite",
    )
    invoice_date: str | None = Field(
        default=None,
        description="Date d'émission au format AAAA-MM-JJ. Lis la date selon le pays de la facture : JJ/MM en Europe, MM/JJ aux États-Unis.",
    )
    amount_excl_tax: float | None = Field(default=None, description="Total HT")
    vat_amount: float | None = Field(default=None, description="Total TVA")
    amount_incl_tax: float | None = Field(default=None, description="Total TTC")
    currency: str | None = Field(
        default=None, description="Code devise ISO à 3 lettres (EUR, USD, GBP…)"
    )


class ExtractionError(Exception):
    pass


class InvoiceExtractor(Protocol):
    def extract(self, text: str, pdf: bytes) -> ExtractedInvoice: ...


class GeminiExtractor:
    def __init__(self, api_key: str | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def extract(self, text: str, pdf: bytes) -> ExtractedInvoice:
        if not self.api_key:
            raise ExtractionError("Clé GEMINI_API_KEY manquante dans .env")

        from google import genai
        from google.genai import errors, types

        client = genai.Client(api_key=self.api_key)
        contents: list[types.PartUnionDict] = [
            types.Part.from_bytes(data=pdf, mime_type="application/pdf"),
            PROMPT + (text or "(aucun texte extrait)"),
        ]
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
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
