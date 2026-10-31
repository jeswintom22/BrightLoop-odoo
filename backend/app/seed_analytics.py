"""Database seeder for realistic product analytics, subscription plans,
variants, discounts, invoices, and payments.
"""

import datetime as dt
from decimal import Decimal
import uuid
from sqlalchemy.orm import Session

from app.core.time import utc_now, business_date
from app.models.tax import TaxConfiguration
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.subscription_plan import SubscriptionPlan
from app.models.discount import Discount
from app.modules.billing.models import Invoice, InvoiceLine, Payment


def run_seed(db: Session) -> dict:
    today = business_date()
    now = utc_now()

    # 1. Tax configuration
    gst_tax = db.query(TaxConfiguration).filter(TaxConfiguration.name == "GST 18%").first()
    if not gst_tax:
        gst_tax = TaxConfiguration(name="GST 18%", tax_percentage=Decimal("18.00"), is_active=True)
        db.add(gst_tax)
        db.flush()

    # 2. Products
    products_data = [
        {
            "name": "Cloud ERP Pro",
            "product_type": "subscription",
            "sales_price": Decimal("3000.00"),
            "cost_price": Decimal("800.00"),
            "notes": "Flagship multi-tenant ERP platform for modern fast-growing businesses.",
            "is_active": True,
            "tax_id": gst_tax.id,
        },
        {
            "name": "Custom Workflow Automation",
            "product_type": "service",
            "sales_price": Decimal("1500.00"),
            "cost_price": Decimal("450.00"),
            "notes": "Low-code custom business logic orchestration and webhook connectors.",
            "is_active": True,
            "tax_id": gst_tax.id,
        },
        {
            "name": "API Gateway Enterprise",
            "product_type": "digital",
            "sales_price": Decimal("5000.00"),
            "cost_price": Decimal("1200.00"),
            "notes": "High-throughput API gateway with global edge rate-limiting and telemetry.",
            "is_active": True,
            "tax_id": gst_tax.id,
        },
        {
            "name": "Dedicated Database Node",
            "product_type": "digital",
            "sales_price": Decimal("3500.00"),
            "cost_price": Decimal("2100.00"),
            "notes": "Managed dedicated PostgreSQL instance with automated daily snapshots.",
            "is_active": True,
            "tax_id": gst_tax.id,
        },
        {
            "name": "Legacy Storage Addon",
            "product_type": "goods",
            "sales_price": Decimal("500.00"),
            "cost_price": Decimal("580.00"),  # Negative unit margin (-16%)
            "notes": "Cold storage block storage add-on for historical logs archiving.",
            "is_active": True,
            "tax_id": gst_tax.id,
        },
        {
            "name": "Email Marketing Starter",
            "product_type": "service",
            "sales_price": Decimal("800.00"),
            "cost_price": Decimal("720.00"),  # Low profit margin (10%)
            "notes": "Transactional and blast email automation starter suite.",
            "is_active": True,
            "tax_id": gst_tax.id,
        },
        {
            "name": "Executive Consulting Hours",
            "product_type": "service",
            "sales_price": Decimal("6000.00"),
            "cost_price": Decimal("2800.00"),  # Zero active subscribers
            "notes": "Dedicated 1-on-1 strategic technology advisory and architecture audit.",
            "is_active": True,
            "tax_id": gst_tax.id,
        },
    ]

    product_map = {}
    for p_info in products_data:
        p = db.query(Product).filter(Product.name == p_info["name"]).first()
        if not p:
            p = Product(**p_info)
            db.add(p)
            db.flush()
        else:
            for k, v in p_info.items():
                setattr(p, k, v)
        product_map[p.name] = p

    # 3. Variants
    variants_data = [
        {"product": "Cloud ERP Pro", "name": "5 Users Starter", "sku": "ERP-05", "sales_price": Decimal("3000.00"), "cost_price": Decimal("800.00")},
        {"product": "Cloud ERP Pro", "name": "15 Users Team", "sku": "ERP-15", "sales_price": Decimal("6000.00"), "cost_price": Decimal("1500.00")},
        {"product": "Cloud ERP Pro", "name": "Unlimited Enterprise", "sku": "ERP-UNL", "sales_price": Decimal("12000.00"), "cost_price": Decimal("2800.00")},
        {"product": "API Gateway Enterprise", "name": "100k Monthly Calls", "sku": "API-100K", "sales_price": Decimal("5000.00"), "cost_price": Decimal("1200.00")},
        {"product": "API Gateway Enterprise", "name": "1M Monthly Calls", "sku": "API-1M", "sales_price": Decimal("13000.00"), "cost_price": Decimal("2900.00")},
        {"product": "Dedicated Database Node", "name": "16GB Standard Node", "sku": "DB-16G", "sales_price": Decimal("3500.00"), "cost_price": Decimal("2100.00")},
        {"product": "Dedicated Database Node", "name": "32GB High-Mem Node", "sku": "DB-32G", "sales_price": Decimal("6500.00"), "cost_price": Decimal("3800.00")},
    ]

    for v_info in variants_data:
        parent = product_map[v_info["product"]]
        v = db.query(ProductVariant).filter(ProductVariant.sku == v_info["sku"]).first()
        if not v:
            v = ProductVariant(
                product_id=parent.id,
                name=v_info["name"],
                sku=v_info["sku"],
                sales_price=v_info["sales_price"],
                cost_price=v_info["cost_price"],
                is_active=True,
            )
            db.add(v)
            db.flush()

    # 4. Subscription Plans
    plans_data = [
        {
            "product": "Cloud ERP Pro",
            "name": "ERP Monthly Growth",
            "price": Decimal("3000.00"),
            "billing_frequency": "monthly",
            "minimum_quantity": 4,
            "start_date": today - dt.timedelta(days=120),
            "status": "active",
        },
        {
            "product": "Cloud ERP Pro",
            "name": "ERP Annual Enterprise",
            "price": Decimal("30000.00"),
            "billing_frequency": "yearly",
            "minimum_quantity": 2,
            "start_date": today - dt.timedelta(days=180),
            "status": "active",
        },
        {
            "product": "Custom Workflow Automation",
            "name": "Automation Weekly Sprint",
            "price": Decimal("400.00"),
            "billing_frequency": "weekly",
            "minimum_quantity": 3,
            "start_date": today - dt.timedelta(days=60),
            "status": "active",
        },
        {
            "product": "API Gateway Enterprise",
            "name": "API Enterprise Monthly",
            "price": Decimal("5000.00"),
            "billing_frequency": "monthly",
            "minimum_quantity": 3,
            "start_date": today - dt.timedelta(days=90),
            "status": "active",
        },
        {
            "product": "Dedicated Database Node",
            "name": "DB Monthly Standard",
            "price": Decimal("3500.00"),
            "billing_frequency": "monthly",
            "minimum_quantity": 2,
            "start_date": today - dt.timedelta(days=90),
            "status": "active",
        },
        {
            "product": "Legacy Storage Addon",
            "name": "Legacy Storage Retention Plan",
            "price": Decimal("500.00"),
            "billing_frequency": "monthly",
            "minimum_quantity": 1,
            "start_date": today - dt.timedelta(days=45),
            "status": "active",
        },
    ]

    for pl_info in plans_data:
        parent = product_map[pl_info["product"]]
        pl = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == pl_info["name"]).first()
        if not pl:
            pl = SubscriptionPlan(
                product_id=parent.id,
                name=pl_info["name"],
                price=pl_info["price"],
                billing_frequency=pl_info["billing_frequency"],
                minimum_quantity=pl_info["minimum_quantity"],
                start_date=pl_info["start_date"],
                status=pl_info["status"],
            )
            db.add(pl)
            db.flush()

    # 5. Discounts
    discounts_data = [
        {
            "name": "Launch Special 50%",
            "code": "LAUNCH50",
            "discount_type": "percentage",
            "discount_value": Decimal("50.00"),
            "start_date": now - dt.timedelta(days=90),
            "expiry_date": now + dt.timedelta(days=60),
            "min_purchase_amount": Decimal("1000.00"),
            "usage_limit": 100,
            "usage_count": 82,
            "is_active": True,
        },
        {
            "name": "Flat ₹500 Off Enterprise",
            "code": "FLAT500",
            "discount_type": "fixed_amount",
            "discount_value": Decimal("500.00"),
            "start_date": now - dt.timedelta(days=60),
            "expiry_date": now + dt.timedelta(days=30),
            "min_purchase_amount": Decimal("2500.00"),
            "usage_limit": 50,
            "usage_count": 48,  # Near capacity: 96%
            "is_active": True,
        },
        {
            "name": "Early Bird Founder 20%",
            "code": "EARLYBIRD",
            "discount_type": "percentage",
            "discount_value": Decimal("20.00"),
            "start_date": now - dt.timedelta(days=120),
            "expiry_date": now + dt.timedelta(days=15),
            "min_purchase_amount": Decimal("500.00"),
            "usage_limit": 30,
            "usage_count": 30,  # Exhausted: 100%
            "is_active": True,
        },
        {
            "name": "Summer Retention 10%",
            "code": "SUMMER10",
            "discount_type": "percentage",
            "discount_value": Decimal("10.00"),
            "start_date": now - dt.timedelta(days=20),
            "expiry_date": now + dt.timedelta(days=70),
            "min_purchase_amount": Decimal("0.00"),
            "usage_limit": 200,
            "usage_count": 14,  # Available
            "is_active": True,
        },
    ]

    for d_info in discounts_data:
        d = db.query(Discount).filter(Discount.code == d_info["code"]).first()
        if not d:
            d = Discount(**d_info)
            db.add(d)
            db.flush()

    # 6. Sample historical Invoices and Payments
    existing_invoices = db.query(Invoice).count()
    if existing_invoices < 5:
        customer_id = uuid.UUID("00000000-0000-4000-8000-000000000101")
        sample_runs = [
            (today - dt.timedelta(days=90), product_map["Cloud ERP Pro"], 3, Decimal("9000.00")),
            (today - dt.timedelta(days=60), product_map["Cloud ERP Pro"], 4, Decimal("12000.00")),
            (today - dt.timedelta(days=60), product_map["API Gateway Enterprise"], 2, Decimal("10000.00")),
            (today - dt.timedelta(days=30), product_map["Cloud ERP Pro"], 4, Decimal("12000.00")),
            (today - dt.timedelta(days=30), product_map["Custom Workflow Automation"], 3, Decimal("4500.00")),
            (today - dt.timedelta(days=30), product_map["Dedicated Database Node"], 2, Decimal("7000.00")),
            (today - dt.timedelta(days=5), product_map["Cloud ERP Pro"], 4, Decimal("12000.00")),
            (today - dt.timedelta(days=5), product_map["Legacy Storage Addon"], 2, Decimal("1000.00")),
            (today - dt.timedelta(days=5), product_map["API Gateway Enterprise"], 3, Decimal("15000.00")),
        ]

        inv_num = 200
        for issue_d, prod, qty, subtotal in sample_runs:
            inv_num += 1
            # Exact clean numbers without floating-point mismatch
            tax = Decimal("0.00")
            disc = Decimal("0.00")
            total = subtotal

            inv = Invoice(
                invoice_number=f"INV-2026-{inv_num:05d}",
                customer_id=customer_id,
                status="paid",
                issue_date=issue_d,
                due_date=issue_d + dt.timedelta(days=14),
                period_start=issue_d,
                period_end=issue_d + dt.timedelta(days=30),
                currency="INR",
                subtotal=subtotal,
                tax_total=tax,
                discount_total=disc,
                total_amount=total,
                amount_paid=total,
            )
            db.add(inv)
            db.flush()

            # Line
            line = InvoiceLine(
                invoice_id=inv.id,
                product_id=uuid.UUID(f"00000000-0000-4000-8000-{prod.id:012d}"),
                description=f"{prod.name} (Monthly)",
                position=0,
                quantity=Decimal(str(qty)),
                unit_price=prod.sales_price,
                subtotal=subtotal,
                tax_amount=tax,
                discount_amount=disc,
                line_total=total,
            )
            db.add(line)
            db.flush()

            # Payment
            pmt = Payment(
                payment_reference=f"PAY-2026-{inv_num:05d}",
                invoice_id=inv.id,
                amount=total,
                method="bank_transfer",
                status="posted",
                paid_at=dt.datetime.combine(issue_d + dt.timedelta(days=2), dt.time(10, 0), tzinfo=dt.timezone.utc),
            )
            db.add(pmt)

    db.commit()

    return {
        "products_count": db.query(Product).count(),
        "variants_count": db.query(ProductVariant).count(),
        "plans_count": db.query(SubscriptionPlan).count(),
        "discounts_count": db.query(Discount).count(),
        "invoices_count": db.query(Invoice).count(),
    }


if __name__ == "__main__":
    from app.core.database import SessionLocal
    with SessionLocal() as session:
        res = run_seed(session)
        print("Analytics seed completed successfully:", res)
