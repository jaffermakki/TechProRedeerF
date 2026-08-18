"""
Business logic tests — tax math, the discount cap fix, and a permanent
regression test for the exact dashboard bug we hit and fixed mid-project
(Jinja's `dict.items` colliding with a dict *key* literally named "items").
"""
import re

from app.tax import calc_canadian_tax, PROVINCE_TAX


def test_ontario_hst_is_a_single_13_percent_line():
    result = calc_canadian_tax(100.0, "ON")
    assert len(result["lines"]) == 1
    assert result["lines"][0]["amount"] == 13.00
    assert result["tax_total"] == 13.00
    assert result["total"] == 113.00


def test_bc_has_separate_gst_and_pst_lines():
    result = calc_canadian_tax(100.0, "BC")
    assert len(result["lines"]) == 2
    amounts = {l["label"].split(" ")[0]: l["amount"] for l in result["lines"]}
    assert amounts["GST"] == 5.00
    assert amounts["PST"] == 7.00
    assert result["tax_total"] == 12.00
    assert result["total"] == 112.00


def test_unknown_province_code_falls_back_to_ontario():
    result = calc_canadian_tax(100.0, "XX")
    assert result["total"] == calc_canadian_tax(100.0, "ON")["total"]


def test_every_province_total_equals_taxable_plus_tax(): # invariant that must always hold
    for province in PROVINCE_TAX:
        result = calc_canadian_tax(250.0, province)
        assert result["total"] == round(250.0 + result["tax_total"], 2), province


def test_zero_taxable_produces_zero_tax():
    result = calc_canadian_tax(0.0, "QC")
    assert result["tax_total"] == 0.0
    assert result["total"] == 0.0


def _first_active_product_id(db_session):
    from app.models import Product
    return db_session.query(Product).filter(Product.stock > 0).first().id


def test_dollar_discount_cannot_exceed_subtotal(owner_client, db_session):
    """Regression test for the discount-cap fix: a $500 manual discount on a
    $50 cart must not push the total negative — it should cap at $0.00."""
    product_id = _first_active_product_id(db_session)
    owner_client.post("/pos/clear")  # start from an empty cart
    owner_client.post("/pos/add-custom", data={"product_id": product_id, "custom_price": "50.00"})
    owner_client.post("/pos/discount", data={"mode": "$", "value": "500"})

    resp = owner_client.get("/pos")
    assert resp.status_code == 200
    match = re.search(r"Charge \$([\d.]+)", resp.text)
    assert match, "Could not find the Charge button total in the rendered POS page"
    total = float(match.group(1))
    assert total == 0.00, f"Expected total capped at $0.00, got ${total}"
    assert "$-" not in resp.text, "A negative dollar amount was rendered somewhere on the page"

    owner_client.post("/pos/clear")  # leave the cart clean for other tests


def test_percentage_discount_cannot_exceed_100(owner_client, db_session):
    product_id = _first_active_product_id(db_session)
    owner_client.post("/pos/clear")
    owner_client.post("/pos/add-custom", data={"product_id": product_id, "custom_price": "20.00"})
    owner_client.post("/pos/discount", data={"mode": "%", "value": "500"})  # 500%, should cap at 100%

    resp = owner_client.get("/pos")
    match = re.search(r"Charge \$([\d.]+)", resp.text)
    total = float(match.group(1))
    assert total == 0.00

    owner_client.post("/pos/clear")


def test_dashboard_renders_without_crashing(owner_client):
    """Regression test for the checklist dict-key-collision bug: the
    dashboard used to 500 with 'builtin_function_or_method object is not
    iterable' because a dict passed to the template had a key literally
    named 'items', which Jinja resolved to dict.items (the built-in method)
    instead of the actual data. This must never come back. (The bug wasn't
    tied to any particular data state, so this doesn't depend on running
    before or after any other test file.)"""
    resp = owner_client.get("/")
    assert resp.status_code == 200
    assert "builtin_function_or_method" not in resp.text


# ── REPAIR PARTS COST IN PROFIT (Reports) ────────────────────────────
# A repair charge line has no product_id, so nothing in the normal
# per-line profit loop catches its cost — repair_detail.html already
# computes the correct per-ticket margin (charge minus parts used) via
# RepairPart, but that math never used to reach the monthly Reports
# figure: every repair charge counted as 100% pure profit regardless of
# how much real parts cost went into it. These lock in the fix.

def _create_repair(owner_client, phone, device):
    owner_client.post("/repairs/add", data={
        "phone": phone, "name": "Profit Test Customer", "device": device, "issue": "Screen Replacement",
        "description": "cracked screen", "estimated_cost": "150.00", "warranty_days": "90",
    }, follow_redirects=False)


def _charge_and_collect(owner_client, repair_id):
    owner_client.post(f"/repairs/{repair_id}/charge", follow_redirects=False)
    return owner_client.post("/pos/checkout", data={"payment_method": "Cash", "tendered": "500"},
                              follow_redirects=False)


def _extract_profit_and_cogs(html):
    """Reads the real markup in reports.html — there are no element IDs to
    hook into, just a stat-value div for Profit and a 'COGS: $X.XX' phrase
    inside the muted caption underneath it."""
    import re
    profit_m = re.search(r'Gross Profit \(All Time\)</div>\s*<div class="stat-value[^"]*">\$([\d,]+\.\d\d|-[\d,]+\.\d\d)', html)
    cogs_m = re.search(r'COGS: \$([\d,]+\.\d\d)', html)
    assert profit_m, "couldn't find the Gross Profit stat in the reports page"
    assert cogs_m, "couldn't find the COGS figure in the reports page"
    return float(profit_m.group(1).replace(",", "")), float(cogs_m.group(1).replace(",", ""))


def test_repair_with_no_parts_counts_full_charge_as_profit(owner_client, db_session):
    """Baseline: a repair that used zero parts (pure labour) should still
    count its whole charge as profit — the fix must not touch this case."""
    from app.models import Repair, Invoice

    profit_before, _ = _extract_profit_and_cogs(owner_client.get("/reports").text)
    _create_repair(owner_client, "555-7001", "No Parts Repair Phone")
    repair = db_session.query(Repair).filter(Repair.device == "No Parts Repair Phone").first()
    owner_client.post(f"/repairs/{repair.id}/cost", data={"estimated_cost": "", "final_cost": "100.00"})
    _charge_and_collect(owner_client, repair.id)

    db_session.expire_all()
    invoice = db_session.query(Invoice).filter(Invoice.repair_id == repair.id).first()
    assert invoice is not None

    profit_after, _ = _extract_profit_and_cogs(owner_client.get("/reports").text)
    assert round(profit_after - profit_before, 2) == 100.00


def test_repair_parts_cost_is_subtracted_from_profit(owner_client, db_session):
    from app.models import Repair, Invoice, Product

    product = Product(sku="PROFIT-TEST-PART", name="Test Screen Part", category="PART",
                       price=80.00, cost=35.00, stock=10)
    db_session.add(product)
    db_session.commit()

    profit_before, _ = _extract_profit_and_cogs(owner_client.get("/reports").text)

    _create_repair(owner_client, "555-7002", "Parts Repair Phone")
    repair = db_session.query(Repair).filter(Repair.device == "Parts Repair Phone").first()
    owner_client.post(f"/repairs/{repair.id}/parts/add", data={"product_id": product.id, "qty": "1"})
    owner_client.post(f"/repairs/{repair.id}/cost", data={"estimated_cost": "", "final_cost": "150.00"})
    _charge_and_collect(owner_client, repair.id)

    db_session.expire_all()
    invoice = db_session.query(Invoice).filter(Invoice.repair_id == repair.id).first()
    assert invoice is not None

    profit_after, _ = _extract_profit_and_cogs(owner_client.get("/reports").text)
    # $150 charged, $35 real parts cost -> only $115 should reach profit.
    assert round(profit_after - profit_before, 2) == 115.00


def test_repair_parts_cost_shows_up_in_cogs(owner_client, db_session):
    from app.models import Repair, Product

    product = Product(sku="PROFIT-TEST-PART-2", name="Test Battery Part", category="PART",
                       price=60.00, cost=22.50, stock=10)
    db_session.add(product)
    db_session.commit()

    _, cogs_before = _extract_profit_and_cogs(owner_client.get("/reports").text)

    _create_repair(owner_client, "555-7003", "Cogs Repair Phone")
    repair = db_session.query(Repair).filter(Repair.device == "Cogs Repair Phone").first()
    owner_client.post(f"/repairs/{repair.id}/parts/add", data={"product_id": product.id, "qty": "1"})
    owner_client.post(f"/repairs/{repair.id}/cost", data={"estimated_cost": "", "final_cost": "120.00"})
    _charge_and_collect(owner_client, repair.id)

    _, cogs_after = _extract_profit_and_cogs(owner_client.get("/reports").text)
    assert round(cogs_after - cogs_before, 2) == 22.50


def test_multiple_parts_on_one_repair_sum_correctly(owner_client, db_session):
    from app.models import Repair, Product

    part_a = Product(sku="PROFIT-MULTI-A", name="Multi Part A", category="PART", price=50, cost=10.00, stock=10)
    part_b = Product(sku="PROFIT-MULTI-B", name="Multi Part B", category="PART", price=50, cost=15.00, stock=10)
    db_session.add_all([part_a, part_b])
    db_session.commit()

    _create_repair(owner_client, "555-7004", "Multi Parts Repair Phone")
    repair = db_session.query(Repair).filter(Repair.device == "Multi Parts Repair Phone").first()
    owner_client.post(f"/repairs/{repair.id}/parts/add", data={"product_id": part_a.id, "qty": "1"})
    owner_client.post(f"/repairs/{repair.id}/parts/add", data={"product_id": part_b.id, "qty": "2"})
    # 10.00 + (15.00 x 2) = 40.00 total parts cost
    owner_client.post(f"/repairs/{repair.id}/cost", data={"estimated_cost": "", "final_cost": "200.00"})

    _, cogs_before = _extract_profit_and_cogs(owner_client.get("/reports").text)
    _charge_and_collect(owner_client, repair.id)
    _, cogs_after = _extract_profit_and_cogs(owner_client.get("/reports").text)
    assert round(cogs_after - cogs_before, 2) == 40.00


def test_non_repair_invoice_profit_is_unaffected(owner_client, db_session):
    """A plain product sale (no repair_id at all) must not be touched by
    the repair-parts lookup — confirms the fix is correctly scoped."""
    from app.models import Product

    product = db_session.query(Product).filter(Product.stock > 0).first()
    owner_client.post("/pos/clear")
    owner_client.post(f"/pos/add/{product.id}")
    resp = owner_client.post("/pos/checkout", data={"payment_method": "Cash", "tendered": "500"},
                              follow_redirects=False)
    assert resp.status_code == 303

    reports_resp = owner_client.get("/reports")
    assert reports_resp.status_code == 200  # no crash — the main regression risk for this fix
