"""Idempotent Stripe catalog setup for Testify subscription plans."""
import os
import stripe
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

CATALOG = [
    {
        "product_key": "testify_pro",
        "name": "Testify Pro",
        "tax_code": "txcd_10103001",  # SaaS
        "prices": [
            {"lookup_key": "pro_monthly", "amount": 2900, "currency": "nzd", "interval": "month"},
            {"lookup_key": "pro_yearly", "amount": 29000, "currency": "nzd", "interval": "year"},
        ],
    },
    {
        "product_key": "testify_business",
        "name": "Testify Business",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "business_monthly", "amount": 7900, "currency": "nzd", "interval": "month"},
            {"lookup_key": "business_yearly", "amount": 79000, "currency": "nzd", "interval": "year"},
        ],
    },
]


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("product_key") == entry["product_key"]:
            return p
    return stripe.Product.create(
        name=entry["name"], tax_code=entry.get("tax_code"),
        metadata={"managed_by": "testify", "product_key": entry["product_key"]},
    )


def ensure_tax_settings():
    s = stripe.tax.Settings.retrieve()
    if s.head_office and getattr(s.head_office, "address", None):
        return
    try:
        stripe.tax.Settings.modify(
            head_office={"address": {"country": "US", "line1": "1 Market St", "city": "San Francisco", "state": "CA", "postal_code": "94105"}},
            defaults={"tax_behavior": "exclusive"},
        )
    except Exception as e:
        print("tax settings skip:", e)


def main():
    ensure_tax_settings()
    for entry in CATALOG:
        product = get_or_create_product(entry)
        for p in entry["prices"]:
            existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
            if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
                stripe.Price.modify(existing[0].id, active=False)
                existing = []
            if not existing:
                kwargs = dict(product=product.id, unit_amount=p["amount"], currency=p["currency"],
                              lookup_key=p["lookup_key"], transfer_lookup_key=True)
                if p.get("interval"):
                    kwargs["recurring"] = {"interval": p["interval"]}
                stripe.Price.create(**kwargs)
                print(f"created price {p['lookup_key']}")
            else:
                print(f"price {p['lookup_key']} ok")
    print("STRIPE CATALOG READY")


if __name__ == "__main__":
    main()
