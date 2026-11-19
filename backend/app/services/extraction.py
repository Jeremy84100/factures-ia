from functools import cache
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from google import genai

PROMPT = """Tu es un assistant comptable. Tu reçois un document d'achat en PDF : une facture, un avoir, un bon de commande ou un bon de livraison.
Lis-le entièrement : le logo, l'en-tête, la mise en page et les tableaux.
Règles :
- Recopie les valeurs telles qu'elles figurent sur le document. N'invente jamais rien : si une valeur est absente ou illisible, mets null.
- Les montants et les quantités sont des nombres avec un point décimal, sans symbole (1234.50). Un avoir a des montants négatifs.
- Une ligne par article, dans l'ordre du document. Les sous-totaux, totaux, acomptes et la TVA ne sont jamais des lignes. Des frais de port ou une écotaxe écrits sur une ligne à part sont des lignes.
"""

DocumentType = Literal["facture", "bon_de_commande", "bon_de_livraison", "autre"]
DeliveryModeName = Literal["retrait", "standard", "express"]


class ExtractedLine(BaseModel):
    reference: str | None = Field(
        default=None,
        description="Référence ou code de l'article, recopié tel quel. null s'il n'y en a pas.",
    )
    description: str | None = Field(
        default=None, description="Désignation de l'article"
    )
    quantity: float | None = Field(
        default=None,
        description="Quantité de la ligne. Sur un bon de livraison : la quantité livrée, jamais la quantité commandée ni le reliquat.",
    )
    unit: str | None = Field(default=None, description="Unité (u, m, kg, h, lot…)")
    unit_price: float | None = Field(
        default=None,
        description="Prix unitaire HT après remise de ligne. null si le document n'a pas de prix, comme souvent un bon de livraison.",
    )
    amount_excl_tax: float | None = Field(
        default=None, description="Montant HT de la ligne"
    )


class ExtractedDocument(BaseModel):
    document_type: DocumentType | None = Field(
        default=None,
        description="facture (y compris avoir, reçu, ticket, note d'hôtel, invoice, Rechnung, bill), bon_de_commande (commande d'achat, purchase order), bon_de_livraison (bon de livraison, bordereau de livraison, delivery note, Lieferschein) ou autre",
    )
    title: str | None = Field(
        default=None,
        description="Titre du document recopié tel qu'il est imprimé en haut (« FACTURE », « AVOIR », « Facture d'avoir », « BON DE LIVRAISON », « Gutschrift », « Credit note »…). null s'il n'y en a pas.",
    )
    supplier: str | None = Field(
        default=None,
        description="Raison sociale de l'entreprise qui vend : celle qui émet la facture ou le bon de livraison, celle à qui le bon de commande est adressé. Jamais l'acheteur, jamais une personne de contact.",
    )
    supplier_country: str | None = Field(
        default=None,
        description="Pays de l'adresse du fournisseur, en code ISO à 2 lettres (FR, BE, DE, ES, IT, GB, US…). null si l'adresse n'indique pas le pays et que rien ne permet de le savoir.",
    )
    number: str | None = Field(
        default=None,
        description="Numéro du document lui-même : numéro de facture, d'avoir, de commande ou de bon de livraison",
    )
    date_raw: str | None = Field(
        default=None,
        description="Date du document recopiée exactement comme elle est écrite",
    )
    date: str | None = Field(
        default=None,
        description="Date du document au format AAAA-MM-JJ. Lis la date selon le pays du document : JJ/MM en Europe, MM/JJ aux États-Unis.",
    )
    order_reference: str | None = Field(
        default=None,
        description="Numéro de la commande d'achat à laquelle se rapporte une facture ou un bon de livraison (« Votre commande », « Réf. commande », « N° commande client », « PO »). null sur un bon de commande, et jamais le numéro du document lui-même.",
    )
    amount_excl_tax: float | None = Field(default=None, description="Total HT")
    vat_amount: float | None = Field(default=None, description="Total TVA")
    amount_incl_tax: float | None = Field(
        default=None,
        description="Total TTC de ce document, pas le montant restant à payer qui peut inclure des arriérés ou des acomptes",
    )
    currency: str | None = Field(
        default=None, description="Code devise ISO à 3 lettres (EUR, USD, GBP…)"
    )
    is_credit_note: bool | None = Field(
        default=None,
        description="true si le document est un avoir (credit note, Gutschrift) qui rembourse le client, false sinon",
    )
    vat_exemption: str | None = Field(
        default=None,
        description="Mention qui justifie l'absence de TVA, recopiée telle quelle (« TVA non applicable, art. 293 B du CGI », « Autoliquidation », « Exonération de TVA, article 262 ter I du CGI », « §4 UStG »…). null si le document n'en contient pas.",
    )
    delivery_method: str | None = Field(
        default=None,
        description="Mode de livraison recopié tel quel (« Livraison sur chantier », « Retrait en agence », « Express 24 h », « Transporteur »…). null si le document n'en parle pas.",
    )
    delivery_mode: DeliveryModeName | None = Field(
        default=None,
        description="Le même mode de livraison rangé dans une catégorie : retrait (le client vient lui-même chercher la marchandise : retrait, enlèvement, comptoir, click and collect), express (livraison urgente, express, 24 h, chronopost), standard (toute autre livraison faite par le fournisseur ou un transporteur, y compris « livraison dépôt », « livraison chantier » ou « livraison au dépôt » : le mot livraison veut dire que le fournisseur apporte). null si le document n'en parle pas.",
    )
    expected_delivery_date: str | None = Field(
        default=None,
        description="Sur un bon de commande : date de livraison souhaitée, promise ou prévue, au format AAAA-MM-JJ. Jamais la date du document. null si absente.",
    )
    due_date: str | None = Field(
        default=None,
        description="Sur une facture : date d'échéance ou date limite de paiement écrite sur le document, au format AAAA-MM-JJ. Ne la calcule jamais : null si aucune date d'échéance n'est écrite.",
    )
    payment_terms: str | None = Field(
        default=None,
        description="Sur une facture : conditions ou délai de paiement recopiés tels quels (« 30 jours », « 45 jours fin de mois », « à réception », « comptant »). null si le document n'en parle pas.",
    )
    iban: str | None = Field(
        default=None,
        description="Sur une facture : IBAN du fournisseur, le compte où le payer, recopié tel qu'il est écrit. Jamais l'IBAN du client (prélèvement, mandat SEPA, « votre compte »), jamais un IBAN masqué par des étoiles. null s'il n'y en a pas.",
    )
    supplier_email: str | None = Field(
        default=None,
        description="Adresse e-mail du fournisseur écrite sur le document (contact, comptabilité, service client). Jamais celle de l'acheteur. null s'il n'y en a pas.",
    )
    lines: list[ExtractedLine] = Field(
        default_factory=list, description="Lignes d'articles du document"
    )


class ExtractionError(Exception):
    pass


class DocumentExtractor(Protocol):
    def extract(self, pdf: bytes) -> ExtractedDocument: ...


@cache
def _gemini_client(api_key: str) -> genai.Client:
    from google import genai

    return genai.Client(api_key=api_key)


class GeminiExtractor:
    def __init__(self, api_key: str | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def extract(self, pdf: bytes) -> ExtractedDocument:
        if not self.api_key:
            raise ExtractionError("Clé GEMINI_API_KEY manquante dans .env")

        from google.genai import errors, types

        client = _gemini_client(self.api_key)
        contents: list[types.PartUnionDict] = [
            types.Part.from_bytes(data=pdf, mime_type="application/pdf"),
            PROMPT,
        ]
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedDocument,
                    temperature=0,
                ),
            )
        except errors.APIError as e:
            raise ExtractionError(f"Erreur de l'API Gemini : {e.message}") from e

        if not isinstance(response.parsed, ExtractedDocument):
            raise ExtractionError("Réponse de Gemini illisible")
        return response.parsed
