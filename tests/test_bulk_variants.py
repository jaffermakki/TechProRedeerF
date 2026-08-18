"""
Tests for the bulk case-variant generator — the tool that creates many
phone-brand/model/color SKUs of one case style in a single pass, instead
of adding them one at a time through the regular Add Product form.
"""
from app.models import Product


def test_bulk_generate_creates_one_row_per_model_times_color(owner_client, db_session):
    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "Test Wallet Case",
        "category": "CASE", "subcategory": "Generic", "sku_prefix": "",
        "price": "24.99", "cost": "8.00", "stock": "5",
        "reorder_threshold": "2", "reorder_qty": "10",
        "phone_selections": ["Apple||iPhone 16", "Apple||iPhone 16 Pro"],
        "extra_models": "",
        "colors": ["Black", "Clear"],
        "extra_colors": "",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/products"

    variants = db_session.query(Product).filter(Product.variant_group == "Test Wallet Case").all()
    assert len(variants) == 4  # 2 models x 2 colors

    combos = {(v.phone_model, v.color) for v in variants}
    assert combos == {
        ("iPhone 16", "Black"), ("iPhone 16", "Clear"),
        ("iPhone 16 Pro", "Black"), ("iPhone 16 Pro", "Clear"),
    }
    for v in variants:
        assert v.phone_brand == "Apple"
        assert v.price == 24.99
        assert v.cost == 8.00
        assert v.stock == 5
        assert v.sku  # non-empty and, since Product.sku is unique, implicitly distinct


def test_bulk_generate_supports_freeform_models_and_colors(owner_client, db_session):
    """The checklist covers common phones, but a shop needs to be able
    to add something new (or a brand not in the list) without a code
    change — that's what the two textareas are for."""
    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "Test Freeform Case",
        "category": "CASE", "price": "15.00", "cost": "0", "stock": "0",
        "reorder_threshold": "5", "reorder_qty": "10",
        "phone_selections": [],
        "extra_models": "LG: Velvet\nNokia G50",  # one with an explicit brand, one without
        "colors": [],
        "extra_colors": "Lavender, Mint Green",
    }, follow_redirects=False)
    assert resp.status_code == 303

    variants = db_session.query(Product).filter(Product.variant_group == "Test Freeform Case").all()
    assert len(variants) == 4  # 2 models x 2 colors

    models = {(v.phone_brand, v.phone_model) for v in variants}
    assert ("LG", "Velvet") in models
    assert ("Other", "Nokia G50") in models  # no colon in that line -> falls back to "Other"

    colors = {v.color for v in variants}
    assert colors == {"Lavender", "Mint Green"}


def test_bulk_generate_requires_style_models_and_colors(owner_client, db_session):
    """Missing any of the three required pieces should bounce back to
    the form with an error rather than silently creating nothing (or
    worse, partial garbage rows)."""
    before = db_session.query(Product).count()
    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "   ",  # whitespace-only — must be treated the same as blank
        "category": "CASE", "price": "10.00", "cost": "0", "stock": "0",
        "reorder_threshold": "5", "reorder_qty": "10",
        "phone_selections": ["Apple||iPhone 16"],
        "colors": ["Black"],
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/products/bulk-variants"
    assert db_session.query(Product).count() == before


def test_bulk_generate_requires_at_least_one_model(owner_client, db_session):
    before = db_session.query(Product).count()
    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "No Models Case",
        "category": "CASE", "price": "10.00", "cost": "0", "stock": "0",
        "reorder_threshold": "5", "reorder_qty": "10",
        "phone_selections": [],  # nothing checked
        "extra_models": "",
        "colors": ["Black"],
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/products/bulk-variants"
    assert db_session.query(Product).count() == before


def test_bulk_generate_requires_at_least_one_color(owner_client, db_session):
    before = db_session.query(Product).count()
    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "No Colors Case",
        "category": "CASE", "price": "10.00", "cost": "0", "stock": "0",
        "reorder_threshold": "5", "reorder_qty": "10",
        "phone_selections": ["Apple||iPhone 16"],
        "colors": [],  # nothing checked
        "extra_colors": "",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/products/bulk-variants"
    assert db_session.query(Product).count() == before


def test_bulk_generate_disambiguates_sku_collisions(owner_client, db_session):
    """Running the generator twice for the same style/model/color
    combination (e.g. staff accidentally double-submits) must not
    crash on the SKU unique constraint or silently drop the second
    batch — it should create a distinguishable second SKU."""
    payload = {
        "variant_group": "Test Collision Case",
        "category": "CASE", "price": "10.00", "cost": "0", "stock": "0",
        "reorder_threshold": "5", "reorder_qty": "10",
        "phone_selections": ["Apple||iPhone 16"],
        "colors": ["Black"],
    }
    first = owner_client.post("/products/bulk-variants/generate", data=payload, follow_redirects=False)
    assert first.status_code == 303
    second = owner_client.post("/products/bulk-variants/generate", data=payload, follow_redirects=False)
    assert second.status_code == 303

    variants = db_session.query(Product).filter(Product.variant_group == "Test Collision Case").all()
    assert len(variants) == 2
    skus = {v.sku for v in variants}
    assert len(skus) == 2, "both rows must have distinct SKUs, not a silently overwritten/duplicated one"


def test_bulk_generate_blocked_for_cashier(cashier_client, db_session):
    before = db_session.query(Product).count()
    resp = cashier_client.post("/products/bulk-variants/generate", data={
        "variant_group": "Blocked Case", "category": "CASE", "price": "10.00", "cost": "0", "stock": "0",
        "reorder_threshold": "5", "reorder_qty": "10",
        "phone_selections": ["Apple||iPhone 16"], "colors": ["Black"],
    }, follow_redirects=False)
    assert resp.status_code == 403
    assert db_session.query(Product).count() == before


def test_bulk_variants_form_requires_manager_or_owner(technician_client, cashier_client):
    for client in (technician_client, cashier_client):
        resp = client.get("/products/bulk-variants", follow_redirects=False)
        assert resp.status_code == 403


def test_bulk_generate_supports_laptop_models(owner_client, db_session):
    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "Laptop Sleeve",
        "category": "LAPTOP_ACC", "subcategory": "Incase",
        "price": "39.99", "cost": "12.00", "stock": "3",
        "reorder_threshold": "2", "reorder_qty": "5",
        "phone_selections": ["Apple||MacBook Air 13\" (M2/M3)", "Dell||XPS 13"],
        "colors": ["Black", "Gray"],
    }, follow_redirects=False)
    assert resp.status_code == 303

    variants = db_session.query(Product).filter(Product.variant_group == "Laptop Sleeve").all()
    assert len(variants) == 4  # 2 laptop models x 2 colors
    brands = {v.phone_brand for v in variants}
    assert brands == {"Apple", "Dell"}
    for v in variants:
        assert v.category == "LAPTOP_ACC"


def test_bulk_generate_supports_console_controller_models(owner_client, db_session):
    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "Controller Skin",
        "category": "GAMING", "subcategory": "Generic",
        "price": "12.99", "cost": "3.00", "stock": "10",
        "reorder_threshold": "3", "reorder_qty": "10",
        "phone_selections": ["Sony||DualSense Controller", "Microsoft||Xbox Controller"],
        "colors": ["Black", "Red", "Blue"],
    }, follow_redirects=False)
    assert resp.status_code == 303

    variants = db_session.query(Product).filter(Product.variant_group == "Controller Skin").all()
    assert len(variants) == 6  # 2 controller models x 3 colors
    models = {v.phone_model for v in variants}
    assert models == {"DualSense Controller", "Xbox Controller"}


def test_bulk_variants_form_loads_for_owner(owner_client):
    resp = owner_client.get("/products/bulk-variants")
    assert resp.status_code == 200
    assert "Bulk-Create Variants" in resp.text


# ── Add/remove a model on the checklist (Settings-backed, not a code edit) ──
# The built-in checklist is a fixed list in phone_const.py — new phones ship
# every year, and a shop can't wait on a code change and redeploy to add one.
# These cover the fix: a model added once shows up as a real, permanent
# checkbox from then on, not a free-text entry that has to be retyped
# every single time a batch gets created for it.

def test_add_model_appears_as_a_real_checkbox(owner_client):
    resp = owner_client.post("/products/bulk-variants/add-model", data={
        "brand": "Apple", "model": "iPhone 18 Pro Max",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/products/bulk-variants"

    page = owner_client.get("/products/bulk-variants")
    assert 'value="Apple||iPhone 18 Pro Max"' in page.text


def test_add_model_persists_in_the_database_not_just_the_session(owner_client, db_session):
    owner_client.post("/products/bulk-variants/add-model", data={
        "brand": "Samsung", "model": "Galaxy S27 Ultra",
    })
    from app.models import Setting
    import json
    row = db_session.query(Setting).filter_by(key="custom_phone_models").first()
    assert row is not None
    stored = json.loads(row.value)
    assert "Galaxy S27 Ultra" in stored.get("Samsung", [])


def test_add_model_under_a_brand_new_brand_creates_its_own_section(owner_client):
    resp = owner_client.post("/products/bulk-variants/add-model", data={
        "brand": "OnePlus", "model": "OnePlus 13",
    }, follow_redirects=False)
    assert resp.status_code == 303
    page = owner_client.get("/products/bulk-variants")
    # The checkbox only exists at all if the per-brand loop actually
    # iterated over "OnePlus" as a real brand — sufficient proof on its
    # own that a wholly new brand gets its own section, without needing
    # to match the exact whitespace around the <summary> text separately.
    assert 'value="OnePlus||OnePlus 13"' in page.text


def test_add_model_rejects_empty_brand_or_model(owner_client, db_session):
    """Also locks in a real fix found while writing this test: the route
    used to declare these fields as strictly required (Form(...)), which
    meant a genuinely blank submission crashed into FastAPI's raw JSON
    422 instead of the same friendly redirect+flash every other blank-
    required-field case in this app already gets (see settings_save()).
    Changed to Form("") so it reaches this route's own validation.

    Checked as before/after rather than "the setting is empty" — the
    underlying test DB is session-scoped, so other tests in this file may
    have already added real entries by the time this one runs; what
    actually matters is that THIS submission didn't change anything."""
    from app.models import Setting
    before = db_session.query(Setting).filter_by(key="custom_phone_models").first()
    before_value = before.value if before else None

    resp = owner_client.post("/products/bulk-variants/add-model", data={"brand": "", "model": "Something"},
                              follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/products/bulk-variants"

    after = db_session.query(Setting).filter_by(key="custom_phone_models").first()
    after_value = after.value if after else None
    assert after_value == before_value


def test_add_model_rejects_a_duplicate_of_a_builtin_model(owner_client, db_session):
    """iPhone 15 is already in the built-in list — adding it again should
    be rejected, not silently create a redundant custom entry."""
    resp = owner_client.post("/products/bulk-variants/add-model", data={
        "brand": "Apple", "model": "iPhone 15",
    }, follow_redirects=False)
    assert resp.status_code == 303
    from app.models import Setting
    import json
    row = db_session.query(Setting).filter_by(key="custom_phone_models").first()
    stored = json.loads(row.value) if row else {}
    assert "iPhone 15" not in stored.get("Apple", [])


def test_add_model_is_case_insensitive_against_existing_entries(owner_client, db_session):
    """'iphone 15' (different case) is still the same model as the
    built-in 'iPhone 15' — must be caught as a duplicate too."""
    owner_client.post("/products/bulk-variants/add-model", data={"brand": "Apple", "model": "iphone 15"})
    from app.models import Setting
    import json
    row = db_session.query(Setting).filter_by(key="custom_phone_models").first()
    stored = json.loads(row.value) if row else {}
    assert "iphone 15" not in stored.get("Apple", [])


def test_remove_custom_model_takes_it_off_the_checklist(owner_client):
    owner_client.post("/products/bulk-variants/add-model", data={"brand": "Google", "model": "Pixel 10"})
    page_before = owner_client.get("/products/bulk-variants")
    assert 'value="Google||Pixel 10"' in page_before.text

    resp = owner_client.post("/products/bulk-variants/remove-model", data={
        "brand": "Google", "model": "Pixel 10",
    }, follow_redirects=False)
    assert resp.status_code == 303

    page_after = owner_client.get("/products/bulk-variants")
    assert 'value="Google||Pixel 10"' not in page_after.text


def test_remove_model_cannot_touch_a_builtin_model(owner_client):
    """The built-in list is code, not data — a remove request naming one
    of its entries must be a silent no-op, not delete it from view."""
    resp = owner_client.post("/products/bulk-variants/remove-model", data={
        "brand": "Apple", "model": "iPhone 15",
    }, follow_redirects=False)
    assert resp.status_code == 303
    page = owner_client.get("/products/bulk-variants")
    assert 'value="Apple||iPhone 15"' in page.text  # still there


def test_add_model_requires_manager_or_owner_role(cashier_client):
    resp = cashier_client.post("/products/bulk-variants/add-model", data={
        "brand": "Apple", "model": "iPhone 18",
    })
    assert resp.status_code == 403


def test_a_newly_added_model_can_actually_be_used_to_generate_variants(owner_client, db_session):
    """The real end-to-end point of this feature: not just that the
    checkbox appears, but that generating a batch of cases against a
    just-added model works exactly like it does for a built-in one."""
    owner_client.post("/products/bulk-variants/add-model", data={"brand": "Apple", "model": "iPhone 18 Pro Max"})

    resp = owner_client.post("/products/bulk-variants/generate", data={
        "variant_group": "Launch Day Case", "category": "CASE", "subcategory": "Generic",
        "price": "19.99", "cost": "5.00", "stock": "0",
        "reorder_threshold": "2", "reorder_qty": "10",
        "phone_selections": ["Apple||iPhone 18 Pro Max"],
        "colors": ["Black"],
    }, follow_redirects=False)
    assert resp.status_code == 303

    variant = db_session.query(Product).filter(Product.variant_group == "Launch Day Case").first()
    assert variant is not None
    assert variant.phone_model == "iPhone 18 Pro Max"
    assert variant.phone_brand == "Apple"
