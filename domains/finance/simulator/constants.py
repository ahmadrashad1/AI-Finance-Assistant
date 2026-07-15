from __future__ import annotations

from datetime import date
from decimal import Decimal

from domains.finance.simulation import simulation_today

# Fixed anchor -- never datetime.now()/date.today() anywhere in this package.
# Resolved once at import from the platform-wide simulation date
# (domains.finance.simulation), so the seeder, the consistency check, and the
# services all agree on the same "today" (PRD Ch.19, Simulation Date).
SIMULATION_TODAY: date = simulation_today()
DEFAULT_SEED: int = 42

NUM_CUSTOMERS = 25
NUM_VENDORS = 15
NUM_PURCHASE_ORDERS = 40
NUM_INVOICES = 200
NUM_DUPLICATE_INVOICES = 5
NUM_EXPENSE_CLAIMS_PER_EMPLOYEE = 3
NUM_EMPLOYEES = 20

PAYMENT_COVERAGE = 0.70
NUM_VENDOR_INVOICES = 60
VENDOR_PAYMENT_COVERAGE = 0.70
INVOICE_WINDOW_MONTHS = 18

OPENING_CASH_BALANCE = Decimal("750000.00")

# Mirrors the CHECK constraints in domains/finance/models/ -- one place
# each is spelled out, per the design spec.
PAYMENT_TERMS = ("net_15", "net_30", "net_45", "net_60")
ORG_STATUSES = ("active", "inactive")
PO_STATUSES = ("draft", "approved", "received", "cancelled")
INVOICE_STATUSES = ("draft", "sent", "paid", "partially_paid", "overdue", "cancelled")
PAYMENT_METHODS = ("bank_transfer", "check", "credit_card", "cash")
EXPENSE_STATUSES = ("submitted", "approved", "rejected", "reimbursed")

PAYMENT_TERMS_DAYS = {"net_15": 15, "net_30": 30, "net_45": 45, "net_60": 60}

# Per-customer payment-behavior weight, drawn once at generation time to bias
# payment timing and coverage -- not a formal Persona class or scenario-pack
# system (explicitly out of scope, see design spec's Scope Boundary).
BEHAVIOR_WEIGHTS = ("reliable", "average", "slow", "risky")
BEHAVIOR_DAYS_OFFSET = {
    "reliable": (-5, 2),
    "average": (-2, 10),
    "slow": (5, 45),
    "risky": (20, 90),
}

# ---------------------------------------------------------------------------
# Simulator v2 (PRD Ch.19). The v1 pipeline above is frozen: it must keep its
# exact RNG draw order so re-seeding reproduces the data the evaluation
# cassettes and expectations were recorded against. Everything below is
# generated in a second phase from a *separate* RNG stream.
# ---------------------------------------------------------------------------
V2_RNG_SUFFIX = "v2"  # random.Random(f"{seed}:{V2_RNG_SUFFIX}")

NUM_V2_EMPLOYEES = 25  # 20 v1 + 25 v2 = 45 (target 40-60)
NUM_TERMINATED_EMPLOYEES = 3
NUM_V2_EXPENSE_CLAIMS = 280  # 60 v1 + 280 v2 = 340 (target 250-350)
NUM_FIXED_ASSETS = 48
NUM_STANDALONE_REQUISITIONS = 28
PAYROLL_MONTHS = 18
NUM_MAVERICK_POS = 3
NUM_UNMATCHED_BANK_TRANSACTIONS = 12
NUM_UNMIRRORED_PAYMENTS = 3  # customer payments with no bank-statement line
NUM_UNMIRRORED_VENDOR_PAYMENTS = 3
NUM_FULLY_DEPRECIATED_IN_USE = 3
NUM_PLANTED_OVER_LIMIT_CLAIMS = 8
NUM_PLANTED_MISSING_RECEIPT_CLAIMS = 6
NUM_PLANTED_LATE_SUBMISSION_CLAIMS = 7
NUM_DUPLICATE_CLAIM_PAIRS = 2

EMPLOYEE_GRADES = ("junior", "senior", "manager", "director")
SALARY_BANDS = {  # annual, USD
    "junior": (45_000, 65_000),
    "senior": (70_000, 95_000),
    "manager": (100_000, 130_000),
    "director": (140_000, 180_000),
}
PAYROLL_TAX_RATE = Decimal("0.22")
PAYROLL_OTHER_DEDUCTION_RATE = Decimal("0.03")

BUDGET_CATEGORIES = (
    "travel", "meals", "supplies", "software", "training", "payroll", "procurement"
)

# Policy data (seeded into finance.expense_limit_policies etc.; policies are
# DATA, never prompt text).
EXPENSE_LIMITS = {  # category -> grade -> per-claim limit
    "travel": {"junior": 2500, "senior": 3000, "manager": 4000, "director": 6000},
    "meals": {"junior": 150, "senior": 200, "manager": 300, "director": 500},
    "supplies": {"junior": 1000, "senior": 1250, "manager": 1500, "director": 2000},
    "software": {"junior": 1500, "senior": 2000, "manager": 3000, "director": 5000},
    "training": {"junior": 2000, "senior": 2500, "manager": 3500, "director": 5000},
}
RECEIPT_REQUIRED_ABOVE = Decimal("75.00")
SUBMISSION_DEADLINE_DAYS = 30
APPROVAL_THRESHOLDS = {
    "payment": Decimal("25000.00"),
    "purchase_requisition": Decimal("10000.00"),
    "expense_claim": Decimal("1000.00"),
}
DEPRECIATION_POLICIES = {  # asset class -> (method, useful life months)
    "machinery": ("straight_line", 120),
    "vehicle": ("declining_balance", 60),
    "it_equipment": ("straight_line", 36),
    "office_furniture": ("straight_line", 84),
}
ASSET_COST_RANGES = {  # asset class -> (min, max, step)
    "machinery": (20_000, 250_000, 500),
    "vehicle": (25_000, 80_000, 500),
    "it_equipment": (1_500, 15_000, 100),
    "office_furniture": (500, 8_000, 50),
}

SALES_TAX_RATE = Decimal("0.08")  # must equal the rate used by v1 invoice math
TAX_JURISDICTION = "US-Federal"
WIRE_FEE = Decimal("25.00")
MONTHLY_ACCOUNT_FEE = Decimal("45.00")
PAYROLL_ACCOUNT_OPENING_BALANCE = Decimal("50000.00")
RESERVE_ACCOUNT_OPENING_BALANCE = Decimal("1200000.00")
RESERVE_MONTHLY_SWEEP = Decimal("20000.00")
PETTY_CASH_MONTHLY = Decimal("1500.00")
