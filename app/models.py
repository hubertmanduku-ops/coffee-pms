import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------- enums ----
class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    clerk = "clerk"


class ArrangementType(str, enum.Enum):
    purchase = "purchase"
    processing_on_behalf = "processing_on_behalf"


class BatchStatus(str, enum.Enum):
    open = "open"
    processing = "processing"
    completed = "completed"


class StageType(str, enum.Enum):
    pulping = "pulping"
    fermentation = "fermentation"
    washing = "washing"
    soaking = "soaking"
    drying = "drying"
    hulling_milling = "hulling_milling"


class ProductType(str, enum.Enum):
    cherry = "cherry"
    parchment = "parchment"
    green_coffee = "green_coffee"


class TransactionType(str, enum.Enum):
    in_ = "in"
    out = "out"
    transfer_in = "transfer_in"
    transfer_out = "transfer_out"
    adjustment = "adjustment"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    login = "login"
    logout = "logout"


class ParchmentDestination(str, enum.Enum):
    mill = "mill"
    store = "store"


class SettlementStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"


# ---------------------------------------------------------------- models ----
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.clerk)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    location = Column(String(128))
    is_active = Column(Boolean, default=True, nullable=False)

    stock = relationship("WarehouseStock", back_populates="warehouse")


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True)
    farmer_code = Column(String(32), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    phone = Column(String(32))
    national_id = Column(String(32))
    location = Column(String(128))
    default_arrangement = Column(Enum(ArrangementType), default=ArrangementType.purchase)
    bank_account = Column(String(64))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    intakes = relationship("CoffeeIntake", back_populates="farmer")


class CoffeeIntake(Base):
    __tablename__ = "coffee_intakes"

    id = Column(Integer, primary_key=True)
    intake_number = Column(String(32), unique=True, nullable=False, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False)
    intake_date = Column(Date, nullable=False, default=date.today)
    quantity_kg = Column(Numeric(10, 2), nullable=False)
    arrangement_type = Column(Enum(ArrangementType), nullable=False)
    price_per_kg = Column(Numeric(10, 2), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    quality_grade = Column(String(32))
    moisture_content = Column(Numeric(5, 2))
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("Farmer", back_populates="intakes")
    batch = relationship("Batch", back_populates="intakes", foreign_keys=[batch_id])


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True)
    batch_number = Column(String(32), unique=True, nullable=False, index=True)
    batch_date = Column(Date, nullable=False, default=date.today)
    status = Column(Enum(BatchStatus), nullable=False, default=BatchStatus.open)
    total_cherry_kg = Column(Numeric(10, 2), default=0)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    intakes = relationship("CoffeeIntake", back_populates="batch", foreign_keys=[CoffeeIntake.batch_id])
    composition = relationship("BatchIntake", back_populates="batch")
    stages = relationship("ProcessingStage", back_populates="batch")
    outputs = relationship("ProcessingOutput", back_populates="batch")


class BatchIntake(Base):
    """Traceability of which intakes (and therefore which farmers) make up a mixed batch."""

    __tablename__ = "batch_intakes"
    __table_args__ = (UniqueConstraint("intake_id", name="uq_batch_intake_intake"),)

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    intake_id = Column(Integer, ForeignKey("coffee_intakes.id"), nullable=False)
    quantity_kg = Column(Numeric(10, 2), nullable=False)

    batch = relationship("Batch", back_populates="composition")
    intake = relationship("CoffeeIntake")


class ProcessingStage(Base):
    __tablename__ = "processing_stages"

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    stage = Column(Enum(StageType), nullable=False)
    start_datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_datetime = Column(DateTime, nullable=True)
    parameters = Column(Text)
    notes = Column(Text)
    recorded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    batch = relationship("Batch", back_populates="stages")


class ProcessingOutput(Base):
    __tablename__ = "processing_outputs"

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    output_date = Column(Date, nullable=False, default=date.today)
    product_type = Column(Enum(ProductType), nullable=False)
    quantity_kg = Column(Numeric(10, 2), nullable=False)
    moisture_content = Column(Numeric(5, 2))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    destination = Column(Enum(ParchmentDestination), nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    batch = relationship("Batch", back_populates="outputs")
    warehouse = relationship("Warehouse")


class WarehouseStock(Base):
    """Cached running balance per warehouse/product — updated inside each transaction."""

    __tablename__ = "warehouse_stock"
    __table_args__ = (UniqueConstraint("warehouse_id", "product_type", name="uq_wh_product"),)

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    product_type = Column(Enum(ProductType), nullable=False)
    quantity_kg = Column(Numeric(12, 2), nullable=False, default=0)

    warehouse = relationship("Warehouse", back_populates="stock")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    product_type = Column(Enum(ProductType), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    quantity_kg = Column(Numeric(10, 2), nullable=False)
    reference_type = Column(String(64))
    reference_id = Column(Integer)
    transaction_date = Column(Date, nullable=False, default=date.today)
    recorded_by = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    warehouse = relationship("Warehouse")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    expense_date = Column(Date, nullable=False, default=date.today)
    category = Column(String(64), nullable=False)
    description = Column(String(255))
    amount = Column(Numeric(12, 2), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    sale_number = Column(String(32), unique=True, nullable=False, index=True)
    sale_date = Column(Date, nullable=False, default=date.today)
    customer_name = Column(String(128), nullable=False)
    product_type = Column(Enum(ProductType), nullable=False)
    quantity_kg = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    warehouse = relationship("Warehouse")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(64))
    action = Column(Enum(AuditAction), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class CostRateSettings(Base):
    """Singleton (id=1) admin-editable standard-cost rate card for the Costing module.

    Deliberately excludes cherry purchase price — that varies season to season and always
    comes from actual recorded CoffeeIntake data (live) or a one-off planner input, never a
    stored constant.
    """

    __tablename__ = "cost_rate_settings"

    id = Column(Integer, primary_key=True)
    # 6 decimal places (not 4) — the source rate is the repeating decimal 2/11 (0.181818...);
    # truncating to 4 places (0.1818) was enough to visibly throw off the planner's kg-level
    # output on realistic budgets, so this needs the extra precision to reproduce it exactly.
    parchment_outturn_pct = Column(Numeric(8, 6), nullable=False, default=Decimal("0.181818"))
    milling_recovery_pct = Column(Numeric(6, 4), nullable=False, default=Decimal("0.8"))
    # Same reasoning — the source rate is 1/6 (0.166667 repeating).
    pulping_cost_per_kg_cherry = Column(Numeric(10, 6), nullable=False, default=Decimal("0.166667"))
    milling_cost_per_kg_cherry = Column(Numeric(10, 4), nullable=False, default=Decimal("1.024"))
    marketing_cost_per_kg_green = Column(Numeric(10, 4), nullable=False, default=Decimal("11.52"))
    bag_size_kg = Column(Numeric(6, 2), nullable=False, default=Decimal("50"))
    bag_cost = Column(Numeric(10, 2), nullable=False, default=Decimal("350"))
    transport_cost_per_kg_green = Column(Numeric(10, 4), nullable=False, default=Decimal("5"))
    selling_price_usd_per_kg = Column(Numeric(10, 4), nullable=False, default=Decimal("6"))
    fx_rate_kes_per_usd = Column(Numeric(10, 4), nullable=False, default=Decimal("129"))
    loss_ratio_min = Column(Numeric(6, 2), nullable=False, default=Decimal("4.5"))
    loss_ratio_max = Column(Numeric(6, 2), nullable=False, default=Decimal("6.0"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class FarmerSettlement(Base):
    """A finalized (paid) settlement snapshot for a farmer, so the settlement worksheet report
    doesn't keep re-listing amounts that have already been settled."""

    __tablename__ = "farmer_settlements"

    id = Column(Integer, primary_key=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False)
    as_of_date = Column(Date, nullable=False, default=date.today)
    purchase_payable = Column(Numeric(12, 2), nullable=False, default=0)
    pob_output_share_kg = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(Enum(SettlementStatus), nullable=False, default=SettlementStatus.paid)
    paid_date = Column(Date, nullable=False, default=date.today)
    paid_by = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("Farmer")
