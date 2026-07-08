from __future__ import annotations

from datetime import date

# Fixed anchor -- never datetime.now()/date.today() anywhere in this package.
# See design spec S3: re-running the same seed must always produce the same
# data, including which invoices count as overdue, regardless of the real
# calendar date on the machine running it.
SIMULATION_TODAY: date = date(2026, 7, 8)
DEFAULT_SEED: int = 42

NUM_CUSTOMERS = 25
NUM_VENDORS = 15
NUM_PURCHASE_ORDERS = 40
NUM_INVOICES = 200
NUM_DUPLICATE_INVOICES = 5
NUM_EXPENSE_CLAIMS_PER_EMPLOYEE = 3
NUM_EMPLOYEES = 20

PAYMENT_COVERAGE = 0.70
INVOICE_WINDOW_MONTHS = 18

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
