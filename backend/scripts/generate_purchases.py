import json
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from fpdf import FPDF

from app.services.payment_terms import due_from_terms

OUTPUT = Path(__file__).parent.parent / "app" / "demo" / "purchases"
BUYER = "BTP Exemple SARL, 5 chemin des Rotondes, 84000 Avignon"
VAT_RATE = 0.20


@dataclass(frozen=True)
class Line:
    reference: str | None
    description: str
    quantity: float
    unit: str
    price: float


@dataclass(frozen=True)
class Doc:
    kind: str
    number: str
    day: str
    lines: list[Line]
    order_reference: str | None = None
    delivery_method: str | None = None
    delivery_mode: str | None = None
    promised_day: str | None = None
    payment_terms: str | None = None
    due_day: str | None = None


@dataclass
class Case:
    name: str
    supplier: str
    order_number: str
    status: str
    documents: list[Doc] = field(default_factory=list)
    unlinked: list[str] = field(default_factory=list)


def fr(value: float, places: int = 2) -> str:
    return f"{value:,.{places}f}".replace(",", " ").replace(".", ",")


def cents(value: float) -> float:
    return round(value + 1e-9, 2)


def latin(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


CABLE = Line("CAB-R2V-3G25", "Câble R2V 3G2,5 mm² couronne 100 m", 6, "u", 118.40)
GAINE = Line("ICTA-20", "Gaine ICTA Ø20 mm couronne 100 m", 10, "u", 27.90)
DISJ = Line("DJ-16A", "Disjoncteur phase+neutre 16 A", 24, "u", 9.85)
CIMENT = Line("CIM-CEM2-35", "Ciment CEM II 32,5 sac 35 kg", 50, "sac", 8.90)
SABLE = Line("SAB-0-4", "Sable 0/4 lavé big bag 1 t", 4, "u", 62.00)
PARPAING = Line("PAR-20-50", "Parpaing creux 20x20x50", 300, "u", 1.45)
VIS = Line("VIS-TF-4x40", "Vis tête fraisée 4x40 boîte de 500", 12, "bte", 14.20)
CHEVILLE = Line("CHV-8", "Cheville nylon Ø8 boîte de 100", 20, "bte", 6.75)
FORET = Line("FOR-SDS-8", "Foret SDS+ Ø8 longueur 160", 15, "u", 4.60)
TUBE = Line("PER-16-50", "Tube PER nu Ø16 couronne 50 m", 8, "u", 39.50)
RACCORD = Line("RAC-16-12", "Raccord à sertir PER 16 x 1/2", 60, "u", 3.15)
COLLECTEUR = Line("COL-4D", "Collecteur 4 départs 3/4", 4, "u", 47.80)
VANNE = Line("VAN-QT-20", "Vanne quart de tour 20x27", 10, "u", 11.40)
OSB = Line("OSB3-18", "Panneau OSB 3 ép. 18 mm 2500x1250", 40, "u", 31.90)
CHEVRON = Line("CHV-63x75", "Chevron sapin traité 63x75 L 4 m", 50, "u", 12.30)
LAINE = Line("LDV-100", "Laine de verre 100 mm rouleau 6 m²", 30, "rlx", 24.60)
WC = Line("WC-SUS-PK", "Pack WC suspendu bâti-support", 3, "u", 289.00)
LAVABO = Line("LAV-60", "Lavabo céramique 60 cm", 5, "u", 74.50)
MITIGEUR = Line("MIT-LAV", "Mitigeur lavabo chromé", 5, "u", 48.90)
PEINTURE = Line("PEI-BLC-15", "Peinture acrylique blanc mat 15 L", 12, "pot", 79.00)
ENDUIT = Line("END-LIS-25", "Enduit de lissage 25 kg", 10, "sac", 21.40)
ROULEAU = Line("ROU-180", "Rouleau microfibre 180 mm", 20, "u", 8.30)
MEULEUSE = Line("MEU-125", "Meuleuse d'angle 125 mm 1200 W", 2, "u", 119.00)
CARRELAGE = Line("CAR-60-GRS", "Carrelage grès cérame 60x60 gris", 40, "m²", 32.50)
COLLE = Line("COL-C2-25", "Mortier-colle C2 sac 25 kg", 16, "sac", 18.90)
JOINT = Line("JNT-GRS-5", "Joint carrelage gris 5 kg", 6, "u", 12.40)
ISOLANT = Line("PSE-TH38-100", "Panneau isolant PSE Th38 100 mm", 60, "u", 14.80)
FIXATION = Line(
    "CHV-ISO-140", "Cheville à frapper isolant 140 mm boîte de 100", 4, "bte", 22.60
)
EXPRESS = Line("PORT-EXP", "Frais de livraison express 24 h", 1, "forfait", 45.00)
DISQUE = Line(
    "DIS-125-INOX", "Disque à tronçonner inox 125 mm lot de 10", 6, "lot", 17.50
)
FIBRE = Line("FIB-PRO", "Abonnement fibre pro novembre 2026", 1, "mois", 59.90)
MOBILE = Line("MOB-50", "Forfait mobile 50 Go", 3, "ligne", 19.99)


def delivered(*lines: Line) -> list[Line]:
    return list(lines)


CASES = [
    Case(
        "Achat complet et conforme",
        "Électro Provence Distribution",
        "CMD-26-101",
        "to_pay",
        [
            Doc("order", "CMD-26-101", "2026-10-01", [CABLE, GAINE, DISJ]),
            Doc(
                "delivery", "BL-70412", "2026-10-03", [CABLE, GAINE, DISJ], "CMD-26-101"
            ),
            Doc(
                "invoice",
                "FA-26-5531",
                "2026-10-04",
                [CABLE, GAINE, DISJ],
                "CMD-26-101",
            ),
        ],
    ),
    Case(
        "Facturé plus que livré",
        "Matériaux du Comtat",
        "CMD-26-102",
        "dispute",
        [
            Doc("order", "CMD-26-102", "2026-10-02", [CIMENT, SABLE, PARPAING]),
            Doc(
                "delivery",
                "BL-2026-0877",
                "2026-10-06",
                [replace(CIMENT, quantity=45), SABLE, PARPAING],
                "CMD-26-102",
            ),
            Doc(
                "invoice",
                "F-0098812",
                "2026-10-07",
                [CIMENT, SABLE, PARPAING],
                "CMD-26-102",
            ),
        ],
    ),
    Case(
        "Prix facturé plus cher que commandé",
        "Quincaillerie Rhône-Durance",
        "CMD-26-103",
        "dispute",
        [
            Doc("order", "CMD-26-103", "2026-10-05", [VIS, CHEVILLE, FORET]),
            Doc(
                "delivery",
                "BL-55120",
                "2026-10-07",
                [VIS, CHEVILLE, FORET],
                "CMD-26-103",
            ),
            Doc(
                "invoice",
                "FC-26-7740",
                "2026-10-08",
                [VIS, replace(CHEVILLE, price=7.45), FORET],
                "CMD-26-103",
            ),
        ],
    ),
    Case(
        "Article facturé mais jamais commandé",
        "Plomberie Pro Sud",
        "CMD-26-104",
        "dispute",
        [
            Doc("order", "CMD-26-104", "2026-10-06", [TUBE, RACCORD, COLLECTEUR]),
            Doc(
                "delivery",
                "BL-88231",
                "2026-10-09",
                [TUBE, RACCORD, COLLECTEUR],
                "CMD-26-104",
            ),
            Doc(
                "invoice",
                "FA-104552",
                "2026-10-10",
                [TUBE, RACCORD, COLLECTEUR, VANNE],
                "CMD-26-104",
            ),
        ],
    ),
    Case(
        "Livraison en deux fois, une seule facture",
        "Bois & Panneaux Vaucluse",
        "CMD-26-105",
        "to_pay",
        [
            Doc("order", "CMD-26-105", "2026-10-07", [OSB, CHEVRON, LAINE]),
            Doc(
                "delivery",
                "BL-B-3301",
                "2026-10-09",
                [replace(OSB, quantity=25), CHEVRON],
                "CMD-26-105",
            ),
            Doc(
                "delivery",
                "BL-B-3318",
                "2026-10-14",
                [replace(OSB, quantity=15), LAINE],
                "CMD-26-105",
            ),
            Doc(
                "invoice",
                "FBP-26-412",
                "2026-10-15",
                [OSB, CHEVRON, LAINE],
                "CMD-26-105",
            ),
        ],
    ),
    Case(
        "Mêmes articles, désignations différentes",
        "Sanitaire Avignon Négoce",
        "CMD-26-106",
        "to_pay",
        [
            Doc("order", "CMD-26-106", "2026-10-08", [WC, LAVABO, MITIGEUR]),
            Doc(
                "delivery",
                "BL-SAN-9902",
                "2026-10-12",
                [WC, LAVABO, MITIGEUR],
                "CMD-26-106",
            ),
            Doc(
                "invoice",
                "SAN-F-26-1187",
                "2026-10-13",
                [
                    Line(None, "PACK WC SUSPENDU + BATI SUPPORT", 3, "u", 289.00),
                    Line(None, "LAVABO CERAMIQUE BLANC 60CM", 5, "u", 74.50),
                    Line(None, "MITIGEUR LAVABO CHROME", 5, "u", 48.90),
                ],
                "CMD-26-106",
            ),
        ],
    ),
    Case(
        "Bon de livraison sans numéro de commande",
        "Peintures Méditerranée",
        "CMD-26-107",
        "waiting",
        [
            Doc("order", "CMD-26-107", "2026-10-09", [PEINTURE, ENDUIT, ROULEAU]),
            Doc("delivery", "BL-PM-6620", "2026-10-12", [PEINTURE, ENDUIT, ROULEAU]),
            Doc(
                "invoice",
                "PM-26-3390",
                "2026-10-13",
                [PEINTURE, ENDUIT, ROULEAU],
                "CMD-26-107",
            ),
        ],
        unlinked=["BL-PM-6620"],
    ),
    Case(
        "Livraison et facture sans bon de commande",
        "Outillage Delta",
        "CMD-26-108",
        "to_pay",
        [
            Doc(
                "delivery", "BL-OD-1029", "2026-10-14", [MEULEUSE, DISQUE], "CMD-26-108"
            ),
            Doc(
                "invoice",
                "OD-F-26-0731",
                "2026-10-15",
                [MEULEUSE, DISQUE],
                "CMD-26-108",
            ),
        ],
    ),
]

CASES += [
    Case(
        "Livré en retard",
        "Carrelages du Luberon",
        "CMD-26-109",
        "to_pay",
        [
            Doc("order", "CMD-26-109", "2026-10-08", [CARRELAGE, COLLE, JOINT]),
            Doc(
                "delivery",
                "BL-CL-4471",
                "2026-10-19",
                [CARRELAGE, COLLE, JOINT],
                "CMD-26-109",
            ),
            Doc(
                "invoice",
                "CL-26-0912",
                "2026-10-20",
                [CARRELAGE, COLLE, JOINT],
                "CMD-26-109",
            ),
        ],
    ),
    Case(
        "Express commandé, livré en standard",
        "Isolation Ventoux Pro",
        "CMD-26-110",
        "dispute",
        [
            Doc("order", "CMD-26-110", "2026-10-09", [ISOLANT, FIXATION, EXPRESS]),
            Doc(
                "delivery",
                "BL-IVP-2208",
                "2026-10-13",
                [ISOLANT, FIXATION],
                "CMD-26-110",
            ),
            Doc(
                "invoice",
                "IVP-F-26-377",
                "2026-10-14",
                [ISOLANT, FIXATION, EXPRESS],
                "CMD-26-110",
            ),
        ],
    ),
    Case(
        "Facture seule, sans commande ni livraison",
        "Télécom Pro Provence",
        "TPP-2611-0458",
        "to_pay",
        [
            Doc(
                "invoice",
                "TPP-2611-0458",
                "2026-11-02",
                [FIBRE, MOBILE],
            ),
        ],
    ),
]

# How each invoice is to be paid: terms as written, due date when printed.
PAYMENT = {
    "FA-26-5531": ("Paiement à 45 jours", None),
    "F-0098812": ("30 jours fin de mois", None),
    "FC-26-7740": ("Virement à 45 jours", None),
    "FA-104552": ("30 jours", None),
    "FBP-26-412": ("60 jours", "2026-12-14"),
    "SAN-F-26-1187": ("Paiement à 30 jours", None),
    "PM-26-3390": ("45 jours", None),
    "CL-26-0912": ("45 jours fin de mois", None),
    "IVP-F-26-377": ("Paiement à réception de facture", None),
    "TPP-2611-0458": ("Prélèvement à échéance", "2026-11-20"),
}

# How each document is delivered: written method, mode, promised date (orders).
DELIVERY = {
    "CMD-26-101": ("Livraison sur chantier", "standard", "2026-10-03"),
    "BL-70412": ("Livraison chantier", "standard", None),
    "CMD-26-102": ("Livraison par camion-grue", "standard", "2026-10-06"),
    "BL-2026-0877": ("Camion-grue", "standard", None),
    "CMD-26-103": ("Retrait au comptoir", "pickup", "2026-10-07"),
    "BL-55120": ("Enlèvement par le client", "pickup", None),
    "CMD-26-104": ("Transporteur", "standard", "2026-10-09"),
    "BL-88231": ("Messagerie transporteur", "standard", None),
    "CMD-26-105": ("Livraison sur chantier", "standard", "2026-10-14"),
    "BL-B-3301": ("Livraison chantier", "standard", None),
    "BL-B-3318": ("Livraison chantier", "standard", None),
    "CMD-26-106": ("Livraison au dépôt", "standard", "2026-10-12"),
    "BL-SAN-9902": ("Livraison dépôt", "standard", None),
    "CMD-26-107": ("Retrait en agence", "pickup", "2026-10-12"),
    "BL-PM-6620": ("Retrait en agence", "pickup", None),
    "BL-OD-1029": ("Livraison standard", "standard", None),
    "CMD-26-109": ("Livraison sur chantier", "standard", "2026-10-12"),
    "BL-CL-4471": ("Livraison chantier", "standard", None),
    "CMD-26-110": ("Livraison express 24 h", "express", "2026-10-10"),
    "BL-IVP-2208": ("Livraison standard J+3", "standard", None),
}
for _case in CASES:
    _case.documents = [
        replace(
            doc,
            delivery_method=DELIVERY[doc.number][0],
            delivery_mode=DELIVERY[doc.number][1],
            promised_day=DELIVERY[doc.number][2],
        )
        if doc.number in DELIVERY
        else doc
        for doc in _case.documents
    ]
    _case.documents = [
        replace(
            doc,
            payment_terms=PAYMENT[doc.number][0],
            due_day=PAYMENT[doc.number][1],
        )
        if doc.number in PAYMENT
        else doc
        for doc in _case.documents
    ]

TITLES = {
    "order": "BON DE COMMANDE",
    "delivery": "BON DE LIVRAISON",
    "invoice": "FACTURE",
}


def draw(case: Case, index: int, doc: Doc) -> FPDF:
    pdf = FPDF()
    pdf.add_page()
    y, m, d = doc.day.split("-")

    pdf.set_font("Helvetica", "B", 16)
    issuer = "BTP Exemple SARL" if doc.kind == "order" else case.supplier
    pdf.cell(0, 9, latin(issuer), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    address = (
        "5 chemin des Rotondes, 84000 Avignon"
        if doc.kind == "order"
        else f"ZA de Courtine, lot {10 + index}, 84000 Avignon"
    )
    pdf.cell(0, 5, latin(address), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(
        0,
        8,
        latin(f"{TITLES[doc.kind]} N° {doc.number}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Date : {d}/{m}/{y}", new_x="LMARGIN", new_y="NEXT")
    if doc.kind == "order":
        pdf.cell(
            0, 6, latin(f"Fournisseur : {case.supplier}"), new_x="LMARGIN", new_y="NEXT"
        )
        if doc.delivery_method:
            pdf.cell(
                0,
                6,
                latin(f"Livraison : {doc.delivery_method}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        if doc.promised_day:
            py, pm, pd = doc.promised_day.split("-")
            pdf.cell(
                0,
                6,
                latin(f"Livraison souhaitée le : {pd}/{pm}/{py}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
    else:
        pdf.cell(0, 6, latin(f"Client : {BUYER}"), new_x="LMARGIN", new_y="NEXT")
        if doc.order_reference:
            pdf.cell(
                0,
                6,
                latin(f"Votre commande : {doc.order_reference}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        if doc.kind == "delivery" and doc.delivery_method:
            pdf.cell(
                0,
                6,
                latin(f"Mode de livraison : {doc.delivery_method}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
    pdf.ln(6)

    priced = doc.kind != "delivery"
    widths = [28, 82, 18, 14, 24, 24] if priced else [32, 110, 26, 22]
    headers = (
        ["Réf.", "Désignation", "Qté", "Unité", "PU HT", "Montant HT"]
        if priced
        else ["Réf.", "Désignation", "Qté livrée", "Unité"]
    )
    pdf.set_font("Helvetica", "B", 9)
    for width, header in zip(widths, headers, strict=True):
        pdf.cell(width, 7, latin(header), border=1, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", size=9)
    for line in doc.lines:
        quantity = f"{line.quantity:g}".replace(".", ",")
        cells = [line.reference or "", line.description, quantity, line.unit]
        if priced:
            cells += [fr(line.price), fr(cents(line.quantity * line.price))]
        for position, (width, text) in enumerate(zip(widths, cells, strict=True)):
            align = "R" if position >= 2 else "L"
            pdf.cell(width, 7, latin(text), border=1, align=align)
        pdf.ln()

    if priced:
        excl = cents(sum(cents(line.quantity * line.price) for line in doc.lines))
        vat = cents(excl * VAT_RATE)
        pdf.ln(3)
        for label, value in (
            ("Total HT", excl),
            ("TVA 20 %", vat),
            ("Total TTC", cents(excl + vat)),
        ):
            pdf.cell(166, 6, label, align="R")
            pdf.cell(
                24, 6, f"{fr(value)} EUR", align="R", new_x="LMARGIN", new_y="NEXT"
            )
        if doc.payment_terms:
            pdf.ln(4)
            pdf.cell(
                0,
                6,
                latin(f"Conditions de paiement : {doc.payment_terms}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        if doc.due_day:
            dy, dm, dd = doc.due_day.split("-")
            pdf.cell(
                0,
                6,
                latin(f"Date d'échéance : {dd}/{dm}/{dy}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
    else:
        pdf.ln(10)
        pdf.cell(
            0,
            6,
            latin("Reçu en bon état - signature du client :"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    return pdf


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "-".join(plain.lower().replace("&", " ").split())


def expected_document(case: Case, filename: str, doc: Doc) -> dict[str, object]:
    priced = doc.kind != "delivery"
    lines = [
        {
            "reference": line.reference,
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": line.price if priced else None,
        }
        for line in doc.lines
    ]
    excl = cents(sum(cents(line.quantity * line.price) for line in doc.lines))
    due = doc.due_day or (
        due_from_terms(doc.payment_terms, date.fromisoformat(doc.day))
        if doc.payment_terms
        else None
    )
    return {
        "filename": filename,
        "kind": doc.kind,
        "supplier": case.supplier,
        "number": doc.number,
        "date": doc.day,
        "order_reference": doc.order_reference,
        "delivery_method": doc.delivery_method,
        "delivery_mode": doc.delivery_mode,
        "expected_delivery_date": doc.promised_day,
        "amount_excl_tax": excl if priced else None,
        "payment_terms": doc.payment_terms,
        "due_date": str(due) if due else None,
        "lines": lines,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    expected: dict[str, list[dict[str, object]]] = {"documents": [], "purchases": []}
    for index, case in enumerate(CASES, start=1):
        for doc in case.documents:
            filename = f"{index:02d}-{slug(doc.number)}.pdf"
            draw(case, index, doc).output(str(OUTPUT / filename))
            expected["documents"].append(expected_document(case, filename, doc))
        expected["purchases"].append(
            {
                "case": case.name,
                "order_reference": case.order_number,
                "status": case.status,
                "unlinked": case.unlinked,
            }
        )
    (OUTPUT / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
