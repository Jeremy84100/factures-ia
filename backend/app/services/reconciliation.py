import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from rapidfuzz import fuzz

from app.models import (
    DeliveryMode,
    Document,
    DocumentKind,
    DocumentLine,
    DocumentRef,
    DocumentStatus,
    LineMatch,
    LinkSuggestion,
    Payment,
    Purchase,
    Purchases,
    PurchaseStatus,
    Settlement,
    UnlinkedDocument,
)
from app.services.checks import NO_ORDER_REFERENCE
from app.services.iban import IBAN_CHANGED
from app.services.payment_terms import legal_due_date

QTY_TOLERANCE_PCT = Decimal(0)
PRICE_TOLERANCE = Decimal("0.01")
AMOUNT_TOLERANCE = Decimal("0.02")
DESCRIPTION_MATCH = 85
SUPPLIER_MATCH = 80
CENT = Decimal("0.01")
ZERO = Decimal(0)

USABLE = (DocumentStatus.ok, DocumentStatus.to_check)
PURCHASE_KINDS = (DocumentKind.order, DocumentKind.delivery, DocumentKind.invoice)
MODE_LABELS = {
    DeliveryMode.pickup: "retrait",
    DeliveryMode.standard: "livraison standard",
    DeliveryMode.express: "livraison express",
}
STATUS_ORDER = {
    PurchaseStatus.dispute: 0,
    PurchaseStatus.waiting: 1,
    PurchaseStatus.to_pay: 2,
    PurchaseStatus.paid: 3,
}
KIND_NAMES = {
    DocumentKind.order: "Commande",
    DocumentKind.delivery: "Livraison",
    DocumentKind.invoice: "Facture",
    DocumentKind.unknown: "Document",
}
# The Purchase field that stays empty while this kind of document is missing.
MISSING = {DocumentKind.delivery: "deliveries", DocumentKind.invoice: "invoices"}
OVERDUE = "Livraison promise le"
UNLINKED_DELIVERY = (
    "Le bon de livraison {} de ce fournisseur n'est pas rangé : c'est peut-être"
    " cette livraison"
)


def fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    plain = re.sub(r"(\d),(\d)", r"\1.\2", plain.lower())
    plain = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", plain)
    return re.sub(r"[^a-z0-9.]+", " ", plain).strip()


NUMBER = re.compile(r"\d+(?:\.\d+)?")
# Shipping fees, eco-taxes and the like never appear on a delivery note. Like
# Odoo's service products, they are paid on the ordered quantity.
FEE = re.compile(
    r"\b(frais|port|transport|livraison|ecotaxe|eco (participation|contribution)"
    r"|deee|emballage|consigne)\b"
)


def similar(a: str, b: str) -> float:
    numbers_a, numbers_b = set(NUMBER.findall(a)), set(NUMBER.findall(b))
    if not (numbers_a <= numbers_b or numbers_b <= numbers_a):
        return 0
    return fuzz.token_set_ratio(a, b)


def reference_key(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", fold(value or "").upper())


def same_supplier(a: str, b: str) -> bool:
    return fuzz.token_set_ratio(fold(a), fold(b)) >= SUPPLIER_MATCH


def quantity(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return ("0" if text == "-0" else text).replace(".", ",")


def euros(value: Decimal) -> str:
    return f"{value.quantize(CENT)} €".replace(".", ",")


def to_ref(document: Document) -> DocumentRef:
    return DocumentRef(
        id=document.id,
        kind=document.kind,
        filename=document.filename,
        number=document.number,
        document_date=document.document_date,
        status=document.status,
    )


@dataclass
class Item:
    label: str
    reference: str | None
    description: str
    ordered: Decimal | None = None
    order_price: Decimal | None = None
    delivered: Decimal = ZERO
    invoiced: Decimal = ZERO
    invoice_prices: list[Decimal] = field(default_factory=list)
    from_order: bool = False

    @property
    def is_fee(self) -> bool:
        return bool(FEE.search(fold(f"{self.description} {self.reference or ''}")))

    def to_match(self, issues: list[str], notes: list[str]) -> LineMatch:
        return LineMatch(
            label=self.label,
            reference=self.reference,
            ordered=self.ordered,
            delivered=self.delivered,
            invoiced=self.invoiced,
            order_price=self.order_price,
            invoice_price=self.invoice_prices[0] if self.invoice_prices else None,
            fee=self.is_fee,
            issues=issues,
            notes=notes,
        )


def label_of(line: DocumentLine) -> str:
    return line.description or line.reference or f"Ligne {line.position + 1}"


def find_item(line: DocumentLine, items: list[Item]) -> Item | None:
    key = reference_key(line.reference)
    if key:
        for item in items:
            if reference_key(item.reference) == key:
                return item

    text = fold(line.description or line.reference or "")
    if not text:
        return None
    scored = [(similar(text, fold(item.description)), item) for item in items]
    candidates = [(score, item) for score, item in scored if score >= DESCRIPTION_MATCH]
    if not candidates:
        return None

    def closeness(candidate: tuple[float, Item]) -> tuple[float, Decimal]:
        score, item = candidate
        if line.unit_price is None or item.order_price is None:
            return (score, ZERO)
        return (score, -abs(line.unit_price - item.order_price))

    return max(candidates, key=closeness)[1]


def new_item(line: DocumentLine) -> Item:
    return Item(
        label=label_of(line),
        reference=line.reference,
        description=line.description or line.reference or "",
    )


def place(line: DocumentLine, items: list[Item]) -> Item:
    item = find_item(line, items)
    if item is None:
        item = new_item(line)
        items.append(item)
    return item


def net_price(line: DocumentLine) -> Decimal | None:
    quantity, amount = line.quantity, line.amount_excl_tax
    if quantity and amount is not None:
        return abs(amount / quantity).quantize(Decimal("0.0001"))
    return line.unit_price


def signed(document: Document, value: Decimal) -> Decimal:
    return -abs(value) if document.is_credit_note else value


def build_items(
    orders: Sequence[Document],
    deliveries: Sequence[Document],
    invoices: Sequence[Document],
) -> list[Item]:
    items: list[Item] = []
    for order in orders:
        for line in order.lines:
            item = place(line, items)
            item.from_order = True
            if line.quantity is not None:
                item.ordered = (item.ordered or ZERO) + line.quantity
            if item.order_price is None:
                item.order_price = net_price(line)
    for delivery in deliveries:
        for line in delivery.lines:
            if line.quantity is not None:
                place(line, items).delivered += line.quantity
    for invoice in invoices:
        for line in invoice.lines:
            item = place(line, items)
            if line.quantity is not None:
                item.invoiced += signed(invoice, abs(line.quantity))
            price = net_price(line)
            if price is not None and not invoice.is_credit_note:
                item.invoice_prices.append(price)
    return items


def check_item(
    item: Item, has_order: bool, has_delivery: bool, has_invoice: bool
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    notes: list[str] = []
    label = item.label

    if has_order and not item.from_order:
        if item.invoiced > 0:
            issues.append(f"{label} : facturé mais pas commandé")
        elif item.delivered > 0:
            issues.append(f"{label} : livré mais pas commandé")
        return issues, notes

    if item.is_fee:
        if has_invoice and item.ordered is not None and item.invoiced > item.ordered:
            issues.append(
                f"{label} : facturé {quantity(item.invoiced)},"
                f" commandé {quantity(item.ordered)}"
            )
    else:
        quantity_issues, quantity_notes = check_quantities(
            item, has_delivery, has_invoice
        )
        issues += quantity_issues
        notes += quantity_notes

    if item.order_price is not None:
        for price in dict.fromkeys(item.invoice_prices):
            gap = price - item.order_price
            if gap > PRICE_TOLERANCE:
                issues.append(
                    f"{label} : prix facturé {euros(price)}"
                    f" au lieu de {euros(item.order_price)} commandé"
                )
            elif gap < -PRICE_TOLERANCE:
                notes.append(
                    f"{label} : prix facturé {euros(price)}, plus bas que"
                    f" les {euros(item.order_price)} commandés"
                )
    return issues, notes


def check_quantities(
    item: Item, has_delivery: bool, has_invoice: bool
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    notes: list[str] = []
    label = item.label

    if item.ordered is not None:
        allowed = item.ordered * (1 + QTY_TOLERANCE_PCT / 100)
        if item.delivered > allowed:
            issues.append(
                f"{label} : livré {quantity(item.delivered)},"
                f" commandé {quantity(item.ordered)}"
            )
        elif has_delivery and item.delivered < item.ordered:
            notes.append(
                f"{label} : reste {quantity(item.ordered - item.delivered)} à livrer"
            )

    if has_invoice and has_delivery and item.invoiced > item.delivered:
        issues.append(
            f"{label} : facturé {quantity(item.invoiced)},"
            f" livré {quantity(item.delivered)}"
        )
    elif (
        has_invoice
        and not has_delivery
        and item.ordered is not None
        and item.invoiced > item.ordered
    ):
        issues.append(
            f"{label} : facturé {quantity(item.invoiced)},"
            f" commandé {quantity(item.ordered)}"
        )
    return issues, notes


def amount_due(
    items: Iterable[Item], has_order: bool, has_delivery: bool
) -> Decimal | None:
    due = ZERO
    for item in items:
        price = item.order_price
        if price is None and item.invoice_prices:
            price = item.invoice_prices[0]
        if price is None:
            return None
        payable = item.invoiced
        if has_delivery and not item.is_fee:
            payable = min(payable, item.delivered)
        if has_order:
            payable = min(payable, item.ordered or ZERO)
        due += payable * price
    return due.quantize(CENT)


def invoiced_total(invoices: Sequence[Document]) -> Decimal | None:
    totals = [invoice.amount_excl_tax for invoice in invoices]
    if not totals or None in totals:
        return None
    return sum((total for total in totals if total is not None), ZERO)


def check_documents(documents: Sequence[Document]) -> list[str]:
    issues = []
    suppliers = list(dict.fromkeys(d.supplier for d in documents if d.supplier))
    if any(not same_supplier(suppliers[0], other) for other in suppliers[1:]):
        issues.append(f"Fournisseurs différents : {' / '.join(suppliers)}")

    currencies = {d.currency for d in documents if d.currency}
    if len(currencies) > 1:
        issues.append(f"Devises différentes : {', '.join(sorted(currencies))}")

    order_dates = [
        d.document_date
        for d in documents
        if d.kind == DocumentKind.order and d.document_date
    ]
    for delivery in documents:
        if (
            delivery.kind == DocumentKind.delivery
            and delivery.document_date
            and order_dates
            and delivery.document_date < min(order_dates)
        ):
            issues.append(f"Livraison « {delivery.filename} » datée avant la commande")
    return issues


def day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def days(count: int) -> str:
    return f"{count} jour{'s' if count > 1 else ''}"


def delivery_method(document: Document) -> str:
    if document.delivery_method:
        return document.delivery_method
    return MODE_LABELS[document.delivery_mode] if document.delivery_mode else "?"


def name(document: Document) -> str:
    return document.number or document.filename


def promised_date(orders: Sequence[Document]) -> date | None:
    return next(
        (o.expected_delivery_date for o in orders if o.expected_delivery_date), None
    )


def check_delivery_mode(
    orders: Sequence[Document], deliveries: Sequence[Document]
) -> list[str]:
    ordered = next((o for o in orders if o.delivery_mode), None)
    if ordered is None:
        return []
    return [
        f"Mode de livraison du {name(d)} : « {delivery_method(d)} » au lieu de"
        f" « {delivery_method(ordered)} » commandé"
        for d in deliveries
        if d.delivery_mode and d.delivery_mode != ordered.delivery_mode
    ]


def late_deliveries(
    orders: Sequence[Document], deliveries: Sequence[Document]
) -> list[str]:
    promised = promised_date(orders)
    if promised is None:
        return []
    return [
        f"{name(d)} livré le {day(d.document_date)},"
        f" {days((d.document_date - promised).days)} après la date promise"
        f" ({day(promised)})"
        for d in deliveries
        if d.document_date and d.document_date > promised
    ]


def missing_delivery(orders: Sequence[Document], today: date) -> str | None:
    promised = promised_date(orders)
    if promised is None or today <= promised:
        return None
    return (
        f"Livraison promise le {day(promised)}, toujours pas reçue"
        f" ({days((today - promised).days)} de retard)"
    )


def all_issues(purchase: Purchase) -> list[str]:
    return [*purchase.issues, *(i for line in purchase.lines for i in line.issues)]


def settles(settlement: Settlement | None, issues: list[str]) -> bool:
    return settlement is not None and sorted(settlement.issues) == sorted(issues)


def incl_total(invoices: Sequence[Document]) -> Decimal | None:
    totals = [invoice.amount_incl_tax for invoice in invoices]
    if not totals or None in totals:
        return None
    return sum((total for total in totals if total is not None), ZERO)


def with_tax(
    amount: Decimal | None, excl: Decimal | None, incl: Decimal | None
) -> Decimal | None:
    """An amount excl. tax turned into incl. tax at the invoices' own rate."""
    if amount is None or not excl or incl is None:
        return None
    return (amount * incl / excl).quantize(CENT)


def doubts(documents: Sequence[Document]) -> list[str]:
    """What the AI was unsure about: the purchase waits until it is checked."""
    return [
        f"{KIND_NAMES[d.kind]} {name(d)} à vérifier : {issue}"
        for d in documents
        if d.status == DocumentStatus.to_check
        for issue in d.issues
        if issue != NO_ORDER_REFERENCE and not issue.startswith(IBAN_CHANGED)
    ]


def iban_warning(invoices: Sequence[Document]) -> tuple[str, Document] | None:
    """A new IBAN not confirmed yet: the purchase waits for a phone call."""
    for invoice in invoices:
        if invoice.status != DocumentStatus.to_check:
            continue
        for issue in invoice.issues:
            if issue.startswith(IBAN_CHANGED):
                return issue, invoice
    return None


def due_of(invoices: Sequence[Document]) -> tuple[date | None, bool]:
    """The earliest due date, and whether it is the legal 30 days by default."""
    dues = [
        (invoice.due_date, False)
        if invoice.due_date
        else (legal_due_date(invoice.document_date), True)
        for invoice in invoices
        if not invoice.is_credit_note and invoice.document_date
    ]
    return min(dues, default=(None, False))


def latest(documents: Sequence[Document], field: str) -> str | None:
    """The value on the most recent document that has one."""
    dated = sorted(documents, key=lambda d: d.document_date or date.min, reverse=True)
    return next((getattr(d, field) for d in dated if getattr(d, field)), None)


def invoice_only_note(invoices: Sequence[Document]) -> str:
    cited = next((i.order_reference for i in invoices if i.order_reference), None)
    if all(i.is_credit_note for i in invoices):
        return "Avoir à déduire de votre prochain paiement à ce fournisseur"
    if cited:
        return (
            f"Elle cite la commande {cited} : déposez la commande ou le bon"
            " de livraison pour les comparer"
        )
    return "Facture seule : rien à comparer, elle est vérifiée seule"


def reconcile(
    key: str,
    documents: Sequence[Document],
    today: date | None = None,
    settlement: Settlement | None = None,
    paid_on: Mapping[str, datetime] | None = None,
) -> Purchase:
    today = today or date.today()
    orders = [d for d in documents if d.kind == DocumentKind.order]
    deliveries = [d for d in documents if d.kind == DocumentKind.delivery]
    invoices = [d for d in documents if d.kind == DocumentKind.invoice]
    has_order, has_delivery, has_invoice = (
        bool(orders),
        bool(deliveries),
        bool(invoices),
    )
    invoice_only = has_invoice and not has_order and not has_delivery

    items = build_items(orders, deliveries, invoices)
    matches: list[LineMatch] = []
    line_issues = 0
    for item in items:
        if invoice_only:
            matches.append(item.to_match([], []))
            continue
        issues, item_notes = check_item(item, has_order, has_delivery, has_invoice)
        line_issues += len(issues)
        matches.append(item.to_match(issues, item_notes))

    warning = iban_warning(invoices)
    unsure = doubts(documents) + ([warning[0]] if warning else [])
    notes = doubts(documents)
    issues = check_documents(documents) + check_delivery_mode(orders, deliveries)
    notes += late_deliveries(orders, deliveries)
    total = invoiced_total(invoices)
    gap = None
    if not invoice_only and has_invoice:
        due = amount_due(items, has_order, has_delivery)
        gap = None if total is None or due is None else total - due
        if gap is not None and gap > AMOUNT_TOLERANCE and not line_issues:
            issues.append(
                f"Total facturé {euros(total or ZERO)} HT au lieu de"
                f" {euros(due or ZERO)}"
            )

    overdue = None
    if invoice_only:
        notes.append(invoice_only_note(invoices))
    else:
        if has_order and not has_delivery:
            overdue = missing_delivery(orders, today)
            notes.append(overdue or "Livraison pas encore reçue")
        if not has_invoice:
            notes.append("Facture pas encore reçue")
        if not has_order and has_delivery and has_invoice:
            notes.append("Pas de bon de commande : facture comparée à la livraison")

    complete = invoice_only or (has_delivery and has_invoice)
    status = (
        PurchaseStatus.to_pay if complete and not unsure else PurchaseStatus.waiting
    )

    # Payments follow the invoices, not the purchase: an invoice filed in
    # another purchase later stays paid.
    paid_on = paid_on or {}
    unpaid = [i for i in invoices if str(i.id) not in paid_on]
    paid = [i for i in invoices if str(i.id) in paid_on]
    if paid and unpaid:
        notes += [
            f"Facture {name(i)} déjà payée le {day(paid_on[str(i.id)].date())}"
            for i in paid
        ]
    due_date, assumed = due_of(unpaid)
    incl = incl_total(invoices)

    reference_doc = (orders or deliveries or invoices)[0]
    reference = (
        reference_doc.number
        if orders or (invoice_only and not reference_doc.order_reference)
        else reference_doc.order_reference
    )
    purchase = Purchase(
        key=key,
        order_reference=reference or key,
        supplier=next((d.supplier for d in [*orders, *documents] if d.supplier), None),
        supplier_id=next(
            (d.supplier_id for d in [*orders, *documents] if d.supplier_id), None
        ),
        status=status,
        orders=[to_ref(d) for d in orders],
        deliveries=[to_ref(d) for d in deliveries],
        invoices=[to_ref(d) for d in invoices],
        lines=matches,
        issues=issues,
        notes=notes,
        late=overdue is not None,
        expected_delivery_date=promised_date(orders),
        invoice_only=invoice_only,
        invoiced_excl_tax=total,
        invoiced_incl_tax=incl,
        to_pay_incl_tax=incl_total(unpaid) if unpaid else ZERO,
        gap_excl_tax=gap,
        gap_incl_tax=with_tax(gap, total, incl),
        due_date=due_date,
        due_date_assumed=assumed,
        iban=latest(invoices, "iban"),
        supplier_email=latest(documents, "supplier_email"),
        iban_warning=warning[0] if warning else None,
        iban_document_id=warning[1].id if warning else None,
    )
    disputed = all_issues(purchase)
    if disputed and settles(settlement, disputed):
        purchase.settled_at = settlement.settled_at if settlement else None
    elif disputed:
        purchase.status = PurchaseStatus.dispute
    if invoices and not unpaid:
        purchase.paid_at = max(paid_on[str(i.id)] for i in invoices)
        if purchase.status == PurchaseStatus.dispute:
            purchase.notes.insert(
                0, f"Déjà payé le {day(purchase.paid_at.date())} : demandez un avoir"
            )
        else:
            purchase.status = PurchaseStatus.paid
    return purchase


def purchase_key(document: Document) -> str:
    if document.kind == DocumentKind.order:
        return reference_key(document.number)
    return reference_key(document.order_reference)


def invoice_key(document: Document) -> str:
    """A purchase made of one invoice that cites no order: keyed by its id."""
    return f"FACTURE-{document.id.hex}"


def suggestions_for(
    document: Document, purchases: Sequence[Purchase]
) -> list[LinkSuggestion]:
    """Purchases of the same supplier that still miss this kind of document."""
    if not document.supplier or document.kind not in MISSING:
        return []
    candidates = [
        p
        for p in purchases
        if p.orders
        and p.supplier
        and same_supplier(document.supplier, p.supplier)
        and not getattr(p, MISSING[document.kind])
    ]
    return [
        LinkSuggestion(
            key=p.key,
            order_reference=p.order_reference,
            order_date=p.orders[0].document_date,
        )
        for p in candidates[:3]
    ]


def build_purchases(
    documents: Iterable[Document],
    today: date | None = None,
    settlements: Mapping[str, Settlement] | None = None,
    payments: Iterable[Payment] = (),
) -> Purchases:
    paid_on = {id: p.paid_at for p in payments for id in p.invoice_ids}
    usable = [d for d in documents if d.kind in PURCHASE_KINDS and d.status in USABLE]
    order_suppliers = [
        d.supplier for d in usable if d.kind == DocumentKind.order and d.supplier
    ]

    groups: dict[str, list[Document]] = {}
    unlinked: list[Document] = []
    for document in usable:
        key = purchase_key(document)
        if key:
            groups.setdefault(key, []).append(document)
        elif document.kind == DocumentKind.delivery or (
            document.supplier
            and any(same_supplier(document.supplier, s) for s in order_suppliers)
        ):
            unlinked.append(document)
        elif document.kind == DocumentKind.invoice:
            groups[invoice_key(document)] = [document]

    purchases = [
        reconcile(
            key,
            docs,
            today,
            (settlements or {}).get(key),
            paid_on,
        )
        for key, docs in groups.items()
    ]

    unlinked_refs = []
    for document in unlinked:
        suggestions = suggestions_for(document, purchases)
        unlinked_refs.append(
            UnlinkedDocument(
                **to_ref(document).model_dump(),
                supplier=document.supplier,
                suggestions=suggestions,
            )
        )
        if document.kind == DocumentKind.delivery:
            for suggestion in suggestions:
                explain_unlinked_delivery(document, purchases, suggestion.key)

    purchases.sort(key=sort_key)
    return Purchases(data=purchases, unlinked=unlinked_refs, count=len(purchases))


def explain_unlinked_delivery(
    delivery: Document, purchases: Sequence[Purchase], key: str
) -> None:
    """« Still not delivered » is wrong when the delivery note is right here,
    only not linked to its order yet."""
    purchase = next(p for p in purchases if p.key == key)
    if not purchase.late:
        return
    purchase.late = False
    purchase.notes = [
        UNLINKED_DELIVERY.format(name(delivery)) if note.startswith(OVERDUE) else note
        for note in purchase.notes
    ]


def sort_key(purchase: Purchase) -> tuple[int, date, str]:
    return (
        STATUS_ORDER[purchase.status],
        purchase.due_date or date.max,
        purchase.order_reference,
    )
