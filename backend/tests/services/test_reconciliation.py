import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.models import (
    DeliveryMode,
    Document,
    DocumentKind,
    DocumentLine,
    DocumentRef,
    DocumentStatus,
    Payment,
    Purchase,
    PurchaseStatus,
)
from app.services.reconciliation import build_purchases, reconcile
from app.services.supplier_email import write_email

OWNER = uuid.uuid4()


def ln(
    description: str,
    quantity: str,
    unit_price: str | None = None,
    reference: str | None = None,
) -> DocumentLine:
    price = None if unit_price is None else Decimal(unit_price)
    amount = (
        None if price is None else (Decimal(quantity) * price).quantize(Decimal("0.01"))
    )
    return DocumentLine(
        reference=reference,
        description=description,
        quantity=Decimal(quantity),
        unit_price=price,
        amount_excl_tax=amount,
    )


def cable(quantity: str = "50", price: str | None = "1.19") -> DocumentLine:
    return ln("Câble R2V 3G2,5 100 m", quantity, price, "CAB-3G25")


def gaine(quantity: str = "100", price: str | None = "0.42") -> DocumentLine:
    return ln("Gaine ICTA 20 mm", quantity, price, "ICTA-20")


def doc(kind: DocumentKind, lines: list[DocumentLine], **fields: object) -> Document:
    values: dict[str, object] = {
        "kind": kind,
        "filename": f"{kind.value}.pdf",
        "file": b"",
        "owner_id": OWNER,
        "status": DocumentStatus.ok,
        "supplier": "Rexel",
        "document_date": date(2026, 10, 2),
        "currency": "EUR",
        "lines": lines,
    }
    if kind == DocumentKind.order:
        values["number"] = "CMD-2041"
    else:
        values["order_reference"] = "CMD-2041"
    if kind == DocumentKind.invoice:
        values["amount_excl_tax"] = sum(
            (line.amount_excl_tax or Decimal(0) for line in lines), Decimal(0)
        )
    values.update(fields)
    return Document(**values)


def order(*lines: DocumentLine, **fields: object) -> Document:
    return doc(DocumentKind.order, list(lines) or [cable(), gaine()], **fields)


def delivery(*lines: DocumentLine, **fields: object) -> Document:
    fields.setdefault("number", "BL-88")
    fields.setdefault("document_date", date(2026, 10, 5))
    default = [cable(price=None), gaine(price=None)]
    return doc(DocumentKind.delivery, list(lines) or default, **fields)


def invoice(*lines: DocumentLine, **fields: object) -> Document:
    fields.setdefault("number", "FA-501")
    fields.setdefault("document_date", date(2026, 10, 6))
    return doc(DocumentKind.invoice, list(lines) or [cable(), gaine()], **fields)


def test_complete_purchase_is_ready_to_pay() -> None:
    purchase = reconcile("CMD2041", [order(), delivery(), invoice()])
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.issues == []
    assert [line.issues for line in purchase.lines] == [[], []]
    assert purchase.gap_excl_tax == Decimal("0.00")
    assert purchase.order_reference == "CMD-2041"
    assert purchase.supplier == "Rexel"


def test_invoiced_more_than_delivered_is_a_dispute() -> None:
    purchase = reconcile(
        "CMD2041",
        [order(), delivery(cable("45", None), gaine(price=None)), invoice()],
    )
    assert purchase.status == PurchaseStatus.dispute
    assert purchase.lines[0].issues == ["Câble R2V 3G2,5 100 m : facturé 50, livré 45"]
    assert purchase.gap_excl_tax == Decimal("5.95")


def test_higher_price_is_a_dispute() -> None:
    purchase = reconcile(
        "CMD2041", [order(), delivery(), invoice(cable(price="1.24"), gaine())]
    )
    assert purchase.status == PurchaseStatus.dispute
    assert purchase.lines[0].issues == [
        "Câble R2V 3G2,5 100 m : prix facturé 1,24 € au lieu de 1,19 € commandé"
    ]


def test_lower_price_is_only_noted() -> None:
    purchase = reconcile(
        "CMD2041", [order(), delivery(), invoice(cable(price="1.10"), gaine())]
    )
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.lines[0].notes == [
        "Câble R2V 3G2,5 100 m : prix facturé 1,10 €, plus bas que les 1,19 € commandés"
    ]


def test_price_cent_rounding_is_tolerated() -> None:
    purchase = reconcile(
        "CMD2041", [order(), delivery(), invoice(cable(price="1.20"), gaine())]
    )
    assert purchase.lines[0].issues == []


def test_invoiced_but_not_ordered_is_a_dispute() -> None:
    extra = ln("Boîte de dérivation", "4", "2.50", "BD-80")
    purchase = reconcile(
        "CMD2041", [order(), delivery(), invoice(cable(), gaine(), extra)]
    )
    assert purchase.status == PurchaseStatus.dispute
    assert purchase.lines[2].issues == [
        "Boîte de dérivation : facturé mais pas commandé"
    ]
    assert purchase.lines[2].ordered is None


def test_delivered_but_not_ordered_is_a_dispute() -> None:
    extra = ln("Boîte de dérivation", "4", reference="BD-80")
    purchase = reconcile(
        "CMD2041",
        [order(), delivery(cable(price=None), gaine(price=None), extra)],
    )
    assert purchase.lines[2].issues == ["Boîte de dérivation : livré mais pas commandé"]


def test_over_delivery_is_a_dispute() -> None:
    purchase = reconcile(
        "CMD2041", [order(), delivery(cable("60", None), gaine(price=None))]
    )
    assert purchase.lines[0].issues == ["Câble R2V 3G2,5 100 m : livré 60, commandé 50"]


def test_partial_deliveries_add_up() -> None:
    first = delivery(cable("30", None), gaine(price=None), number="BL-88")
    second = delivery(cable("20", None), number="BL-91", filename="bl2.pdf")
    purchase = reconcile("CMD2041", [order(), first, second, invoice()])
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.lines[0].delivered == Decimal("50")
    assert len(purchase.deliveries) == 2


def test_partial_delivery_invoiced_as_delivered_can_be_paid() -> None:
    purchase = reconcile(
        "CMD2041",
        [
            order(),
            delivery(cable("45", None), gaine(price=None)),
            invoice(cable("45"), gaine()),
        ],
    )
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.lines[0].notes == ["Câble R2V 3G2,5 100 m : reste 5 à livrer"]


def test_different_names_for_the_same_article_are_matched() -> None:
    ordered = ln("Câble R2V 3G2,5 couronne 100m", "50", "1.19")
    billed = ln("CABLE R2V 3G2.5 100 M", "50", "1.19")
    received = ln("Cable R2V 3G 2,5 - 100m", "50")
    purchase = reconcile(
        "CMD2041",
        [order(ordered), delivery(received), invoice(billed)],
    )
    assert len(purchase.lines) == 1
    assert purchase.status == PurchaseStatus.to_pay


def test_reference_wins_over_description() -> None:
    renamed = ln("Article sans rapport", "50", "1.19", "cab 3g25")
    purchase = reconcile(
        "CMD2041", [order(cable()), delivery(cable(price=None)), invoice(renamed)]
    )
    assert len(purchase.lines) == 1


def test_order_alone_waits() -> None:
    purchase = reconcile("CMD2041", [order()])
    assert purchase.status == PurchaseStatus.waiting
    assert purchase.notes == ["Livraison pas encore reçue", "Facture pas encore reçue"]


def test_invoice_before_delivery_waits() -> None:
    purchase = reconcile("CMD2041", [order(), invoice()])
    assert purchase.status == PurchaseStatus.waiting


def test_invoice_above_order_without_delivery_is_a_dispute() -> None:
    purchase = reconcile("CMD2041", [order(), invoice(cable("80"), gaine())])
    assert purchase.lines[0].issues == [
        "Câble R2V 3G2,5 100 m : facturé 80, commandé 50"
    ]


def test_delivery_and_invoice_without_order() -> None:
    # Many small firms order by phone: no written order is not a fault.
    purchase = reconcile("CMD2041", [delivery(), invoice()])
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.notes == [
        "Pas de bon de commande : facture comparée à la livraison"
    ]


def test_delivery_and_invoice_without_order_still_compared() -> None:
    purchase = reconcile(
        "CMD2041", [delivery(cable("45", None), gaine(price=None)), invoice()]
    )
    assert purchase.status == PurchaseStatus.dispute


def test_credit_note_reduces_what_was_invoiced() -> None:
    credit = invoice(
        cable("5"),
        number="AV-12",
        is_credit_note=True,
        amount_excl_tax=Decimal("-5.95"),
        filename="avoir.pdf",
    )
    purchase = reconcile(
        "CMD2041",
        [order(), delivery(cable("45", None), gaine(price=None)), invoice(), credit],
    )
    assert purchase.lines[0].invoiced == Decimal("45")
    assert purchase.status == PurchaseStatus.to_pay


def test_different_suppliers_are_a_dispute() -> None:
    purchase = reconcile("CMD2041", [order(), delivery(), invoice(supplier="Sonepar")])
    assert purchase.issues == ["Fournisseurs différents : Rexel / Sonepar"]
    assert purchase.status == PurchaseStatus.dispute


def test_supplier_name_variants_are_the_same_supplier() -> None:
    purchase = reconcile(
        "CMD2041", [order(), delivery(supplier="REXEL France SAS"), invoice()]
    )
    assert purchase.issues == []


def test_delivery_dated_before_order_is_a_dispute() -> None:
    early = delivery(document_date=date(2026, 9, 1))
    purchase = reconcile("CMD2041", [order(), early, invoice()])
    assert purchase.issues == ["Livraison « delivery.pdf » datée avant la commande"]


def test_total_above_lines_is_a_dispute() -> None:
    padded = invoice(amount_excl_tax=Decimal("131.50"))
    purchase = reconcile("CMD2041", [order(), delivery(), padded])
    assert purchase.issues == ["Total facturé 131,50 € HT au lieu de 101,50 €"]


def test_documents_are_grouped_by_order_number() -> None:
    result = build_purchases(
        [
            order(),
            delivery(order_reference="cmd 2041"),
            invoice(order_reference="CMD2041"),
        ]
    )
    assert result.count == 1
    assert result.data[0].status == PurchaseStatus.to_pay


def test_documents_without_order_number_must_be_linked() -> None:
    lost_delivery = delivery(order_reference=None)
    rexel_invoice = invoice(order_reference=None)
    edf_invoice = invoice(order_reference=None, supplier="EDF", filename="edf.pdf")
    result = build_purchases([order(), lost_delivery, rexel_invoice, edf_invoice])
    assert [ref.filename for ref in result.unlinked] == ["delivery.pdf", "invoice.pdf"]


def test_unfinished_documents_are_left_out() -> None:
    reading = invoice(status=DocumentStatus.processing)
    failed = delivery(status=DocumentStatus.failed)
    unknown = doc(DocumentKind.unknown, [])
    result = build_purchases([order(), reading, failed, unknown])
    assert result.data[0].invoices == []
    assert result.data[0].deliveries == []


def test_disputes_come_first() -> None:
    other = order(number="CMD-2050")
    result = build_purchases(
        [order(), delivery(), invoice(cable("80"), gaine()), other]
    )
    assert [p.status for p in result.data] == [
        PurchaseStatus.dispute,
        PurchaseStatus.waiting,
    ]


def test_articles_with_other_sizes_are_not_confused() -> None:
    purchase = reconcile(
        "CMD2041",
        [
            order(ln("Gaine ICTA 20 mm", "100", "0.42")),
            delivery(ln("Gaine ICTA 25 mm", "100")),
        ],
    )
    assert len(purchase.lines) == 2
    assert purchase.lines[1].issues == ["Gaine ICTA 25 mm : livré mais pas commandé"]


def test_line_discount_uses_the_net_price() -> None:
    net = ln("Câble R2V 3G2,5 100 m", "50", "1.25", "CAB-3G25")
    net.amount_excl_tax = Decimal("59.50")
    purchase = reconcile("CMD2041", [order(), delivery(), invoice(net, gaine())])
    assert purchase.lines[0].invoice_price == Decimal("1.1900")
    assert purchase.status == PurchaseStatus.to_pay


def test_invoice_alone_citing_an_order_is_checked_alone() -> None:
    result = build_purchases([invoice(order_reference="PO-778")])
    (purchase,) = result.data
    assert purchase.invoice_only
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.notes == [
        "Elle cite la commande PO-778 : déposez la commande ou le bon de"
        " livraison pour les comparer"
    ]


def test_invoice_without_order_is_a_purchase_of_its_own() -> None:
    bill = invoice(order_reference=None, supplier="EDF Pro", number="EDF-11")
    (purchase,) = build_purchases([bill]).data
    assert purchase.key == f"FACTURE-{bill.id.hex}"
    assert purchase.order_reference == "EDF-11"
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.notes == [
        "Facture seule : rien à comparer, elle est vérifiée seule"
    ]


def test_credit_note_alone_is_to_deduct() -> None:
    credit = invoice(
        order_reference=None,
        supplier="EDF Pro",
        is_credit_note=True,
        amount_excl_tax=Decimal("-10.00"),
        amount_incl_tax=Decimal("-12.00"),
    )
    (purchase,) = build_purchases([credit]).data
    assert purchase.to_pay_incl_tax == Decimal("-12.00")
    assert purchase.due_date is None
    assert purchase.notes == [
        "Avoir à déduire de votre prochain paiement à ce fournisseur"
    ]


TODAY = date(2026, 11, 17)


def test_same_delivery_mode_is_fine() -> None:
    purchase = reconcile(
        "CMD2041",
        [
            order(delivery_mode=DeliveryMode.express),
            delivery(delivery_mode=DeliveryMode.express),
            invoice(),
        ],
    )
    assert purchase.status == PurchaseStatus.to_pay


def test_other_delivery_mode_is_a_dispute() -> None:
    purchase = reconcile(
        "CMD2041",
        [
            order(delivery_mode=DeliveryMode.express, delivery_method="Express 24 h"),
            delivery(delivery_mode=DeliveryMode.standard),
            invoice(),
        ],
    )
    assert purchase.status == PurchaseStatus.dispute
    assert purchase.issues == [
        "Mode de livraison du BL-88 : « livraison standard » au lieu de"
        " « Express 24 h » commandé"
    ]


def test_unknown_delivery_mode_is_not_checked() -> None:
    purchase = reconcile(
        "CMD2041", [order(delivery_mode=DeliveryMode.pickup), delivery(), invoice()]
    )
    assert purchase.status == PurchaseStatus.to_pay


def test_late_delivery_is_noted_but_still_payable() -> None:
    purchase = reconcile(
        "CMD2041",
        [order(expected_delivery_date=date(2026, 10, 1)), delivery(), invoice()],
    )
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.notes == [
        "BL-88 livré le 05/10/2026, 4 jours après la date promise (01/10/2026)"
    ]


def test_delivery_on_the_promised_day_is_on_time() -> None:
    purchase = reconcile(
        "CMD2041",
        [order(expected_delivery_date=date(2026, 10, 5)), delivery(), invoice()],
    )
    assert purchase.notes == []


def test_each_late_delivery_is_noted() -> None:
    first = delivery(cable(price=None), document_date=date(2026, 10, 3))
    second = delivery(
        gaine(price=None), number="BL-89", document_date=date(2026, 10, 6)
    )
    purchase = reconcile(
        "CMD2041",
        [order(expected_delivery_date=date(2026, 10, 4)), first, second, invoice()],
    )
    assert purchase.notes == [
        "BL-89 livré le 06/10/2026, 2 jours après la date promise (04/10/2026)"
    ]


def test_missing_delivery_after_the_promised_date_is_late() -> None:
    purchase = reconcile(
        "CMD2041", [order(expected_delivery_date=date(2026, 11, 16))], TODAY
    )
    assert purchase.status == PurchaseStatus.waiting
    assert purchase.notes == [
        "Livraison promise le 16/11/2026, toujours pas reçue (1 jour de retard)",
        "Facture pas encore reçue",
    ]


def test_missing_delivery_before_the_promised_date_is_just_waiting() -> None:
    purchase = reconcile(
        "CMD2041", [order(expected_delivery_date=date(2026, 11, 20))], TODAY
    )
    assert purchase.notes[0] == "Livraison pas encore reçue"


def test_build_purchases_passes_today_along() -> None:
    result = build_purchases([order(expected_delivery_date=date(2026, 11, 7))], TODAY)
    assert result.data[0].notes[0] == (
        "Livraison promise le 07/11/2026, toujours pas reçue (10 jours de retard)"
    )


def port(quantity: str = "1", price: str | None = "45.00") -> DocumentLine:
    return ln("Frais de port", quantity, price, "PORT")


def test_shipping_fees_are_not_expected_on_the_delivery_note() -> None:
    purchase = reconcile(
        "CMD2041",
        [
            order(cable(), gaine(), port()),
            delivery(),
            invoice(cable(), gaine(), port()),
        ],
    )
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.gap_excl_tax == Decimal("0.00")
    assert all(line.notes == [] for line in purchase.lines)
    assert [line.fee for line in purchase.lines] == [False, False, True]


def test_shipping_fees_not_ordered_are_a_dispute() -> None:
    purchase = reconcile(
        "CMD2041", [order(), delivery(), invoice(cable(), gaine(), port())]
    )
    assert purchase.status == PurchaseStatus.dispute
    assert purchase.lines[-1].issues == ["Frais de port : facturé mais pas commandé"]


def test_shipping_fees_invoiced_twice_are_a_dispute() -> None:
    purchase = reconcile(
        "CMD2041",
        [
            order(cable(), gaine(), port()),
            delivery(),
            invoice(cable(), gaine(), port(quantity="2")),
        ],
    )
    assert purchase.lines[-1].issues == ["Frais de port : facturé 2, commandé 1"]


def test_eco_tax_is_a_fee_but_support_is_not() -> None:
    def eco() -> DocumentLine:
        return ln("Éco-participation DEEE", "1", "2.50")

    def support() -> DocumentLine:
        return ln("Bâti-support WC", "1", "120.00")

    purchase = reconcile(
        "CMD2041",
        [
            order(eco(), support()),
            delivery(ln("Bâti-support WC", "1")),
            invoice(eco(), support()),
        ],
    )
    assert purchase.status == PurchaseStatus.to_pay


def test_supplier_email_without_invoice_asks_how_to_fix() -> None:
    purchase = Purchase(
        key="C1",
        order_reference="C-1",
        status=PurchaseStatus.dispute,
        deliveries=[
            DocumentRef(
                id=uuid.uuid4(),
                kind=DocumentKind.delivery,
                filename="bl.pdf",
                number="BL-1",
                status=DocumentStatus.ok,
            ),
            DocumentRef(
                id=uuid.uuid4(),
                kind=DocumentKind.delivery,
                filename="bl2.pdf",
                number="BL-2",
                status=DocumentStatus.ok,
            ),
        ],
        issues=["Câble : livré 60, commandé 50"],
    )
    email = write_email(purchase, "Marie Durand")
    assert email.subject == "Commande C-1 : écarts sur la livraison"
    assert "vos bons de livraison n° BL-1 et BL-2, pour notre commande" in email.body
    assert "- Câble : livré 60, commandé 50" in email.body
    assert "avoir" not in email.body
    assert email.body.endswith("Cordialement,\nMarie Durand")


def payment(*invoices: Document, day: date = date(2026, 11, 3)) -> Payment:
    return Payment(
        owner_id=OWNER,
        purchase_key="CMD2041",
        invoice_ids=[str(i.id) for i in invoices],
        paid_at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC),
    )


def test_amounts_incl_tax() -> None:
    bill = invoice(amount_incl_tax=Decimal("113.40"))
    purchase = reconcile("CMD2041", [order(), delivery(), bill])
    assert purchase.invoiced_excl_tax == Decimal("101.50")
    assert purchase.invoiced_incl_tax == Decimal("113.40")
    assert purchase.to_pay_incl_tax == Decimal("113.40")


def test_overbilled_incl_tax_uses_the_invoice_rate() -> None:
    bill = invoice(cable(), gaine(), amount_incl_tax=Decimal("121.80"))
    purchase = reconcile(
        "CMD2041", [order(), delivery(cable("45", None), gaine(price=None)), bill]
    )
    assert purchase.gap_excl_tax == Decimal("5.95")
    assert purchase.gap_incl_tax == Decimal("7.14")


def test_paid_purchase() -> None:
    bill = invoice()
    purchase = reconcile("CMD2041", [order(), delivery(), bill], payment=payment(bill))
    assert purchase.status == PurchaseStatus.paid
    assert purchase.paid_at is not None
    assert purchase.to_pay_incl_tax == Decimal(0)


def test_an_invoice_after_payment_is_still_to_pay() -> None:
    first = invoice(cable("25"), gaine("50"), amount_incl_tax=Decimal("60.90"))
    second = invoice(
        cable("25"),
        gaine("50"),
        number="FA-2",
        amount_incl_tax=Decimal("60.90"),
        filename="fa2.pdf",
    )
    purchase = reconcile(
        "CMD2041", [order(), delivery(), first, second], payment=payment(first)
    )
    assert purchase.status == PurchaseStatus.to_pay
    assert purchase.to_pay_incl_tax == Decimal("60.90")
    assert purchase.notes[-1].endswith("déjà payée le 03/11/2026")


def test_gap_found_after_payment_is_a_dispute() -> None:
    bill = invoice()
    purchase = reconcile(
        "CMD2041",
        [order(), delivery(cable("45", None), gaine(price=None)), bill],
        payment=payment(bill),
    )
    assert purchase.status == PurchaseStatus.dispute
    assert purchase.notes[0] == "Déjà payé le 03/11/2026 : demandez un avoir"


def test_a_doubt_keeps_the_purchase_waiting() -> None:
    bill = invoice(
        status=DocumentStatus.to_check, issues=["HT + TVA = 120 mais TTC = 121"]
    )
    purchase = reconcile("CMD2041", [order(), delivery(), bill])
    assert purchase.status == PurchaseStatus.waiting
    assert purchase.notes[0] == (
        "Facture FA-501 à vérifier : HT + TVA = 120 mais TTC = 121"
    )


def test_due_date_written_or_legal() -> None:
    written = invoice(due_date=date(2026, 12, 1))
    assert reconcile("CMD2041", [order(), delivery(), written]).due_date == date(
        2026, 12, 1
    )
    nothing = invoice()
    purchase = reconcile("CMD2041", [order(), delivery(), nothing])
    assert purchase.due_date == date(2026, 11, 5)
    assert purchase.due_date_assumed


def test_unlinked_invoice_suggests_the_purchase_waiting_for_it() -> None:
    lost = invoice(order_reference=None, number="FA-9")
    result = build_purchases([order(), delivery(), lost])
    (unlinked,) = result.unlinked
    assert [s.order_reference for s in unlinked.suggestions] == ["CMD-2041"]
