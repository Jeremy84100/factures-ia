import json
import unicodedata
from pathlib import Path

from fpdf import FPDF

OUTPUT = Path(__file__).parent.parent / "tests" / "fixtures" / "invoices"

INVOICES = [
    ("EDF", "FA-2026-0412", "2026-03-04", [("Électricité février", 70.17)], 0.20),
    ("Orange", "OR778812", "2026-03-05", [("Abonnement fibre", 33.33)], 0.20),
    (
        "Boulangerie Martin",
        "BM-114",
        "2026-02-11",
        [("Viennoiseries réunion", 42.65)],
        0.055,
    ),
    (
        "Bureau Vallée Avignon",
        "BV2026-3381",
        "2026-01-19",
        [
            ("Ramettes papier A4 x10", 39.90),
            ("Cartouches encre", 58.00),
            ("Classeurs x20", 24.60),
        ],
        0.20,
    ),
    (
        "Garage du Rhône",
        "GR-0098",
        "2026-04-02",
        [("Révision véhicule", 189.00), ("Pneus x2", 220.00)],
        0.20,
    ),
    (
        "Hôtel du Palais",
        "HP-55021",
        "2026-05-14",
        [("Nuitée", 95.00), ("Petit-déjeuner", 12.00)],
        0.10,
    ),
    (
        "OVHcloud",
        "FR51229433",
        "2026-06-01",
        [("Serveur VPS", 11.99), ("Nom de domaine", 9.99)],
        0.20,
    ),
    (
        "Restaurant La Fourchette",
        "RF-3302",
        "2026-06-20",
        [("Déjeuner client x3", 81.82)],
        0.10,
    ),
    (
        "SNCF Voyageurs",
        "SV9918274",
        "2026-07-08",
        [("Avignon - Lyon A/R", 98.18)],
        0.10,
    ),
    (
        "Cabinet Durand Avocats",
        "CDA-2026-17",
        "2026-08-30",
        [("Conseil juridique 2h", 400.00)],
        0.20,
    ),
    (
        "Imprimerie Provence",
        "IP-7741",
        "2026-09-12",
        [("Cartes de visite x500", 65.00), ("Flyers x1000", 120.00)],
        0.20,
    ),
    ("Free Mobile", "FM-202610-8812", "2026-10-03", [("Forfait mobile", 16.66)], 0.20),
]


def cents(value: float) -> float:
    return round(value + 1e-9, 2)


def fr(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def build(
    index: int,
    supplier: str,
    number: str,
    day: str,
    lines: list[tuple[str, float]],
    rate: float,
) -> dict[str, str | float]:
    excl = cents(sum(price for _, price in lines))
    vat = cents(excl * rate)
    incl = cents(excl + vat)
    y, m, d = day.split("-")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, supplier, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(
        0,
        6,
        f"{12 + index} rue de la République, 84000 Avignon",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0, 6, f"SIRET 8{index:02d}123456000{index % 10}", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, f"FACTURE N° {number}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Date : {d}/{m}/{y}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        "Client : Cabinet Exemple, 1 place de l'Horloge, 84000 Avignon",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(130, 8, "Désignation", border=1)
    pdf.cell(50, 8, "Montant HT", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for label, price in lines:
        pdf.cell(130, 8, label, border=1)
        pdf.cell(
            50,
            8,
            f"{fr(price)} EUR",
            border=1,
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.ln(4)
    for label, value in (
        ("Total HT", excl),
        (f"TVA {fr(rate * 100).rstrip('0').rstrip(',')} %", vat),
        ("Total TTC", incl),
    ):
        pdf.cell(130, 7, label, align="R")
        pdf.cell(50, 7, f"{fr(value)} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    slug = unicodedata.normalize("NFKD", supplier).encode("ascii", "ignore").decode()
    filename = f"{index:02d}-{slug.lower().replace(' ', '-')}.pdf"
    pdf.output(str(OUTPUT / filename))
    return {
        "filename": filename,
        "supplier": supplier,
        "number": number,
        "date": day,
        "amount_excl_tax": excl,
        "vat_amount": vat,
        "amount_incl_tax": incl,
        "currency": "EUR",
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    expected = [build(i + 1, *invoice) for i, invoice in enumerate(INVOICES)]
    (OUTPUT / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
