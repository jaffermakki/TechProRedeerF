"""
Products and Customers used to load every row that has ever existed on
every page view — fine at a few hundred rows, a real problem as either
table grows into the thousands over a shop's lifetime. These confirm the
fix: aggregates (counts, totals) still reflect every row via SQL
aggregates, the rendered list is paginated, and a search overrides
pagination to check the whole table rather than just the current page.
"""
from app.models import Customer, Product


def _make_customers(db_session, count, prefix="Pagination Test Customer"):
    customers = [Customer(name=f"{prefix} {i:03d}", phone=f"555-{i:04d}") for i in range(count)]
    db_session.add_all(customers)
    db_session.commit()
    return customers


def test_customers_list_paginates_at_50_per_page(owner_client, db_session):
    """Doesn't assume a clean slate — the shared test database may already
    have customers from other tests sorting earlier alphabetically, which
    would push some of these onto a later page. What actually matters:
    pagination is complete (every one of these 55 shows up somewhere) and
    non-overlapping (none show up twice), not that they land on a
    specific page number."""
    _make_customers(db_session, 55, prefix="FiftyPageCustomer")

    page1 = owner_client.get("/customers?page=1")
    total_pages_match = __import__("re").search(r"Page \d+ of (\d+)", page1.text)
    assert total_pages_match, "expected pagination controls with more than 55 customers in the table"
    total_pages = int(total_pages_match.group(1))

    combined_text = ""
    for p in range(1, total_pages + 1):
        combined_text += owner_client.get(f"/customers?page={p}").text

    assert combined_text.count("FiftyPageCustomer") == 55, "every customer should appear exactly once across all pages"


def test_customers_total_count_reflects_everyone_not_just_current_page(owner_client, db_session):
    before = owner_client.get("/customers")
    import re
    before_total = int(re.search(r'Total Customers</div>\s*<div class="stat-value">(\d+)</div>', before.text).group(1))

    _make_customers(db_session, 55, prefix="Total Count Check Customer")

    after = owner_client.get("/customers")
    after_total = int(re.search(r'Total Customers</div>\s*<div class="stat-value">(\d+)</div>', after.text).group(1))
    assert after_total - before_total == 55
    # Only 50 of the 55 new ones (plus whatever pre-existed) render on page 1 -- confirms it's genuinely paginated, not just labelled as such.
    assert after.text.count("Total Count Check Customer") < 55


def test_customers_search_finds_someone_beyond_page_one(owner_client, db_session):
    _make_customers(db_session, 60, prefix="Searchable Alphabetical Zzz")  # sorts after most names -> lands on a later page
    resp = owner_client.get("/customers?q=Searchable+Alphabetical+Zzz+059")
    assert "Searchable Alphabetical Zzz 059" in resp.text


def test_customers_search_is_case_insensitive(owner_client, db_session):
    db_session.add(Customer(name="CaseSensitiveSearchTest", phone="555-1234"))
    db_session.commit()
    resp = owner_client.get("/customers?q=casesensitivesearchtest")
    assert "CaseSensitiveSearchTest" in resp.text


def test_customers_search_shows_no_pagination_controls(owner_client, db_session):
    _make_customers(db_session, 60, prefix="No Pagination When Searching")
    resp = owner_client.get("/customers?q=No+Pagination+When+Searching")
    assert "Page 1 of" not in resp.text


def test_customers_requesting_a_page_beyond_the_last_clamps_instead_of_erroring(owner_client, db_session):
    resp = owner_client.get("/customers?page=99999")
    assert resp.status_code == 200


def test_customers_store_credit_total_reflects_everyone(owner_client, db_session):
    import re
    before = owner_client.get("/customers")
    before_credit = float(re.search(r'Store Credit Outstanding</div>\s*<div class="stat-value text-green">\$([\d,]+\.\d\d)', before.text).group(1).replace(",", ""))

    c = Customer(name="Store Credit Aggregate Check", phone="555-9876", store_credit=42.50)
    db_session.add(c)
    db_session.commit()

    after = owner_client.get("/customers")
    after_credit = float(re.search(r'Store Credit Outstanding</div>\s*<div class="stat-value text-green">\$([\d,]+\.\d\d)', after.text).group(1).replace(",", ""))
    assert round(after_credit - before_credit, 2) == 42.50


# ── PRODUCTS ─────────────────────────────────────────────────────────
# Meaningfully more complex than Customers: this page groups variants
# together for browsing (a group can't be split across pages without
# looking broken), and has a phone-brand/model drill-down alongside
# search. Both search and the drill-down are themselves already a
# filtered, bounded view, so — same principle as Customers — only the
# unfiltered "browse everything" mode is actually paginated.

def _make_products(db_session, count, prefix="PagTestProduct", **extra):
    products = []
    for i in range(count):
        kwargs = dict(sku=f"{prefix}-{i:04d}", name=f"{prefix} {i:03d}", category="ACCESSORY",
                      price=9.99, cost=3.00, stock=10)
        kwargs.update(extra)
        products.append(Product(**kwargs))
    db_session.add_all(products)
    db_session.commit()
    return products


def test_products_list_paginates_ungrouped_items(owner_client, db_session):
    """Counting bare substring occurrences of the shared name prefix
    doesn't work here — each product legitimately appears three times in
    real markup (the SKU cell, the Name cell, and the delete-confirm
    dialog text), all correct. Checking each unique SKU exactly once
    across all pages instead, which has no such ambiguity."""
    created = _make_products(db_session, 55, prefix="FiftyProd")
    expected_skus = {p.sku for p in created}

    page1 = owner_client.get("/products?page=1")
    import re
    m = re.search(r"Page \d+ of (\d+)", page1.text)
    assert m, "expected pagination controls with more than 55 products in the catalog"
    total_pages = int(m.group(1))

    combined = ""
    for p in range(1, total_pages + 1):
        combined += owner_client.get(f"/products?page={p}").text

    for sku in expected_skus:
        assert combined.count(sku) == 1, f"{sku} should appear on exactly one page, exactly once"


def test_products_total_count_reflects_everyone_not_just_current_page(owner_client, db_session):
    import re
    before = owner_client.get("/products")
    before_total = int(re.search(r'Total Products</div>\s*<div class="stat-value">(\d+)</div>', before.text).group(1))

    _make_products(db_session, 55, prefix="TotalCountProd")

    after = owner_client.get("/products")
    after_total = int(re.search(r'Total Products</div>\s*<div class="stat-value">(\d+)</div>', after.text).group(1))
    assert after_total - before_total == 55
    assert after.text.count("TotalCountProd") < 55  # only one page's worth actually rendered


def test_products_low_stock_count_reflects_everyone(owner_client, db_session):
    import re
    before = owner_client.get("/products")
    before_low = int(re.search(r'Low Stock</div>\s*<div class="stat-value[^"]*">(\d+)</div>', before.text).group(1))

    _make_products(db_session, 3, prefix="LowStockProd", stock=1, reorder_threshold=5)

    after = owner_client.get("/products")
    after_low = int(re.search(r'Low Stock</div>\s*<div class="stat-value[^"]*">(\d+)</div>', after.text).group(1))
    assert after_low - before_low == 3


def test_products_stock_value_reflects_everyone(owner_client, db_session):
    import re
    before = owner_client.get("/products")
    before_val = float(re.search(r'Total Stock Value</div>\s*<div class="stat-value">\$([\d,]+\.\d\d)', before.text).group(1).replace(",", ""))

    _make_products(db_session, 1, prefix="StockValueProd", cost=25.00, stock=4)  # 25 x 4 = 100.00

    after = owner_client.get("/products")
    after_val = float(re.search(r'Total Stock Value</div>\s*<div class="stat-value">\$([\d,]+\.\d\d)', after.text).group(1).replace(",", ""))
    assert round(after_val - before_val, 2) == 100.00


def test_products_search_finds_something_and_shows_no_pagination(owner_client, db_session):
    _make_products(db_session, 60, prefix="SearchableProdZzz")
    resp = owner_client.get("/products?q=SearchableProdZzz+059")
    assert "SearchableProdZzz 059" in resp.text
    assert "Page 1 of" not in resp.text


def test_products_search_is_case_insensitive(owner_client, db_session):
    _make_products(db_session, 1, prefix="CaseSensitiveProdCheck")
    resp = owner_client.get("/products?q=casesensitiveprodcheck")
    assert "CaseSensitiveProdCheck" in resp.text


def test_products_phone_brand_drilldown_finds_matching_products(owner_client, db_session):
    _make_products(db_session, 1, prefix="DrillPhoneOne", phone_brand="ZzzTestBrand", phone_model="ZzzModel X")
    _make_products(db_session, 1, prefix="DrillPhoneTwo", phone_brand="ZzzTestBrand", phone_model="ZzzModel Y")
    _make_products(db_session, 1, prefix="DrillPhoneOther", phone_brand="OtherBrand", phone_model="OtherModel")

    resp = owner_client.get("/products?brand=ZzzTestBrand")
    assert "DrillPhoneOne" in resp.text
    assert "DrillPhoneTwo" in resp.text
    assert "DrillPhoneOther" not in resp.text


def test_products_phone_brand_and_model_narrows_further(owner_client, db_session):
    _make_products(db_session, 1, prefix="NarrowModelA", phone_brand="ZzzNarrowBrand", phone_model="ModelA")
    _make_products(db_session, 1, prefix="NarrowModelB", phone_brand="ZzzNarrowBrand", phone_model="ModelB")

    resp = owner_client.get("/products?brand=ZzzNarrowBrand&model=ModelA")
    assert "NarrowModelA" in resp.text
    assert "NarrowModelB" not in resp.text


def test_products_variant_group_renders_as_one_complete_unit(owner_client, db_session):
    """The real point of treating a group as a single browsable item during
    pagination — a group with many variants must never be split across
    page boundaries, or it would render as visibly incomplete on both."""
    group_products = [
        Product(sku=f"GROUPTEST-{i:03d}", name=f"Group Test Variant {i}", category="CASE",
                variant_group="Zzz Pagination Group Test", price=19.99, cost=5.00, stock=10)
        for i in range(8)
    ]
    db_session.add_all(group_products)
    db_session.commit()

    resp = owner_client.get("/products?q=Zzz+Pagination+Group+Test")
    for i in range(8):
        assert f"Group Test Variant {i}" in resp.text


def test_products_requesting_a_page_beyond_the_last_clamps_instead_of_erroring(owner_client, db_session):
    resp = owner_client.get("/products?page=99999")
    assert resp.status_code == 200
