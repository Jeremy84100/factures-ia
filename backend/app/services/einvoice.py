"""E-invoices (Factur-X, ZUGFeRD): the figures are in an XML file inside the PDF.

Since 1 September 2026 every French firm must be able to receive them. When
the XML is there, it is read as is: exact figures, in a few milliseconds,
without the AI. Only the lines may be missing (MINIMUM and BASIC WL profiles
carry none): the AI then reads the lines, the XML keeps the header.
"""

import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

import pypdfium2 as pdfium

from app.services.extraction import ExtractedDocument, ExtractedLine

XML_NAMES = {"factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml"}
MAX_XML_SIZE = 1024 * 1024
NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}
# UNTDID 1001: the codes of a credit note.
CREDIT_NOTES = {"81", "83", "261", "262", "296", "308", "381", "396", "532"}
# UN/ECE recommendation 20: the units a supplier uses most.
UNITS = {
    "C62": "u",
    "H87": "u",
    "EA": "u",
    "XPP": "u",
    "KGM": "kg",
    "GRM": "g",
    "TNE": "t",
    "MTR": "m",
    "MTK": "m²",
    "MTQ": "m³",
    "LTR": "L",
    "HUR": "h",
    "DAY": "jour",
    "MON": "mois",
    "SET": "lot",
    "LS": "forfait",
}


def embedded_xml(pdf: bytes) -> bytes | None:
    try:
        document = pdfium.PdfDocument(pdf)
    except pdfium.PdfiumError:
        return None
    try:
        for index in range(document.count_attachments()):
            attachment = document.get_attachment(index)
            if attachment.get_name().lower() in XML_NAMES:
                data = bytes(attachment.get_data())
                return data if len(data) <= MAX_XML_SIZE else None
    finally:
        document.close()
    return None


def text(node: ET.Element | None, path: str) -> str | None:
    if node is None:
        return None
    found = node.find(path, NS)
    if found is None or found.text is None:
        return None
    return " ".join(found.text.split()) or None


def number(node: ET.Element | None, path: str) -> float | None:
    value = text(node, path)
    if value is None:
        return None
    try:
        return float(Decimal(value))
    except InvalidOperation:
        return None


def day(node: ET.Element | None, path: str) -> str | None:
    value = text(node, path)
    if not value or len(value) != 8 or not value.isdigit():
        return None
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def tax_total(settlement: ET.Element | None, currency: str | None) -> float | None:
    """TaxTotalAmount may be given twice, in the invoice and the tax currency."""
    if settlement is None:
        return None
    totals = settlement.findall(
        "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount", NS
    )
    for total in totals:
        if currency is None or total.get("currencyID") in (None, currency):
            try:
                return float(Decimal((total.text or "").strip()))
            except InvalidOperation:
                return None
    return None


def to_line(item: ET.Element) -> ExtractedLine:
    product = item.find("ram:SpecifiedTradeProduct", NS)
    agreement = item.find("ram:SpecifiedLineTradeAgreement", NS)
    price = number(agreement, "ram:NetPriceProductTradePrice/ram:ChargeAmount")
    per = number(agreement, "ram:NetPriceProductTradePrice/ram:BasisQuantity")
    if price is not None and per:
        price = price / per
    quantity = item.find("ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", NS)
    unit = quantity.get("unitCode") if quantity is not None else None
    return ExtractedLine(
        reference=text(product, "ram:SellerAssignedID")
        or text(product, "ram:GlobalID"),
        description=text(product, "ram:Name"),
        quantity=number(item, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity"),
        unit=UNITS.get(unit or "", unit),
        unit_price=price,
        amount_excl_tax=number(
            item,
            "ram:SpecifiedLineTradeSettlement"
            "/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount",
        ),
    )


def parse_cii(xml: bytes) -> ExtractedDocument | None:
    """A Cross Industry Invoice (the XML of Factur-X) as the AI would give it."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    if root.tag != f"{{{NS['rsm']}}}CrossIndustryInvoice":
        return None
    header = root.find("rsm:ExchangedDocument", NS)
    trade = root.find("rsm:SupplyChainTradeTransaction", NS)
    if header is None or trade is None:
        return None
    agreement = trade.find("ram:ApplicableHeaderTradeAgreement", NS)
    settlement = trade.find("ram:ApplicableHeaderTradeSettlement", NS)
    totals = "ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
    currency = text(settlement, "ram:InvoiceCurrencyCode")
    terms = (
        settlement.find("ram:SpecifiedTradePaymentTerms", NS)
        if settlement is not None
        else None
    )
    exemption = (
        text(settlement, "ram:ApplicableTradeTax/ram:ExemptionReason")
        if settlement is not None
        else None
    )
    incl = number(settlement, totals + "ram:GrandTotalAmount")
    return ExtractedDocument(
        document_type="facture",
        supplier=text(agreement, "ram:SellerTradeParty/ram:Name"),
        number=text(header, "ram:ID"),
        date_raw=None,
        date=day(header, "ram:IssueDateTime/udt:DateTimeString"),
        order_reference=text(
            agreement, "ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID"
        ),
        amount_excl_tax=number(settlement, totals + "ram:TaxBasisTotalAmount"),
        vat_amount=tax_total(settlement, currency),
        amount_incl_tax=incl,
        currency=currency,
        # A corrective invoice for less than nothing refunds, like a credit note.
        is_credit_note=text(header, "ram:TypeCode") in CREDIT_NOTES
        or (incl is not None and incl < 0),
        vat_exemption=exemption,
        due_date=day(terms, "ram:DueDateDateTime/udt:DateTimeString"),
        payment_terms=text(terms, "ram:Description"),
        lines=[
            to_line(item)
            for item in trade.findall("ram:IncludedSupplyChainTradeLineItem", NS)
        ],
    )


def read_einvoice(pdf: bytes) -> ExtractedDocument | None:
    xml = embedded_xml(pdf)
    return parse_cii(xml) if xml else None


def merge_lines(
    einvoice: ExtractedDocument, read: ExtractedDocument
) -> ExtractedDocument:
    """The XML header with the lines the AI read, when the XML has none."""
    return einvoice.model_copy(update={"lines": read.lines})
