import math
from typing import Optional, Tuple, List
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.product_variant import ProductVariantCreate, ProductVariantUpdate


class ProductService:
    @staticmethod
    def get_products(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        product_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Product], int, int]:
        """
        Retrieves paginated products with eager-loaded variants, filtering, and search.
        Returns: (items, total_count, total_pages)
        """
        query = select(Product).options(selectinload(Product.variants))

        # Search filter across name and notes
        if search and search.strip():
            search_term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Product.name.ilike(search_term),
                    Product.notes.ilike(search_term)
                )
            )

        if product_type:
            query = query.where(Product.product_type == product_type.lower())

        if is_active is not None:
            query = query.where(Product.is_active == is_active)

        # Count total matching records
        count_stmt = select(func.count()).select_from(query.order_by(None).subquery())
        total = db.scalar(count_stmt) or 0

        # Pagination math
        offset = (page - 1) * page_size
        pages = math.ceil(total / page_size) if total > 0 else 0

        # Execute paginated fetch ordered by newest first
        items = db.scalars(query.order_by(Product.id.desc()).offset(offset).limit(page_size)).all()
        return list(items), total, pages

    @staticmethod
    def get_product_by_id(db: Session, product_id: int) -> Optional[Product]:
        """Fetch a single product by ID including its variants."""
        stmt = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.id == product_id)
        )
        return db.scalar(stmt)

    @staticmethod
    def create_product(db: Session, product_in: ProductCreate) -> Product:
        """Create a new product with optional inline variants."""
        product = Product(
            name=product_in.name,
            product_type=product_in.product_type,
            sales_price=product_in.sales_price,
            cost_price=product_in.cost_price,
            notes=product_in.notes,
            tax_id=product_in.tax_id,
            is_active=product_in.is_active,
        )

        if product_in.variants:
            for v in product_in.variants:
                variant = ProductVariant(
                    name=v.name,
                    sku=v.sku,
                    sales_price=v.sales_price,
                    cost_price=v.cost_price,
                    attributes=v.attributes or {},
                    is_active=v.is_active,
                )
                product.variants.append(variant)

        db.add(product)
        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def update_product(db: Session, product_id: int, product_in: ProductUpdate) -> Optional[Product]:
        """Update an existing product."""
        product = ProductService.get_product_by_id(db, product_id)
        if not product:
            return None

        update_data = product_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def delete_product(db: Session, product_id: int) -> bool:
        """Delete a product. Cascades to product variants automatically."""
        product = db.get(Product, product_id)
        if not product:
            return False

        db.delete(product)
        db.commit()
        return True

    # ----------------------------------------------------
    # Variant Management
    # ----------------------------------------------------

    @staticmethod
    def get_variants_by_product_id(db: Session, product_id: int) -> List[ProductVariant]:
        """Retrieve all variants associated with a given product ID."""
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id)
            .order_by(ProductVariant.id.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_variant_by_id(db: Session, variant_id: int) -> Optional[ProductVariant]:
        """Fetch a specific product variant by ID."""
        return db.get(ProductVariant, variant_id)

    @staticmethod
    def create_variant(
        db: Session, product_id: int, variant_in: ProductVariantCreate
    ) -> Optional[ProductVariant]:
        """Add a new variant to a specific parent product."""
        product = db.get(Product, product_id)
        if not product:
            return None

        variant = ProductVariant(
            product_id=product_id,
            name=variant_in.name,
            sku=variant_in.sku,
            sales_price=variant_in.sales_price,
            cost_price=variant_in.cost_price,
            attributes=variant_in.attributes or {},
            is_active=variant_in.is_active,
        )
        db.add(variant)
        db.commit()
        db.refresh(variant)
        return variant

    @staticmethod
    def update_variant(
        db: Session, variant_id: int, variant_in: ProductVariantUpdate
    ) -> Optional[ProductVariant]:
        """Update an existing product variant."""
        variant = db.get(ProductVariant, variant_id)
        if not variant:
            return None

        update_data = variant_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(variant, field, value)

        db.commit()
        db.refresh(variant)
        return variant

    @staticmethod
    def delete_variant(db: Session, variant_id: int) -> bool:
        """Delete a single product variant."""
        variant = db.get(ProductVariant, variant_id)
        if not variant:
            return False

        db.delete(variant)
        db.commit()
        return True
