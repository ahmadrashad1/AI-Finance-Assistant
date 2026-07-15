from __future__ import annotations

COMPANY_PREFIXES = [
    "Northwind", "Atlas", "Summit", "Cascade", "Vertex", "Harbor", "Granite",
    "Meridian", "Pioneer", "Union", "Beacon", "Cobalt", "Anchor", "Falcon",
    "Redwood", "Sterling", "Horizon", "Titan", "Delta", "Crestline",
]
COMPANY_SUFFIXES = [
    "Manufacturing", "Industries", "Traders", "Logistics", "Supply Co.",
    "Holdings", "Materials", "Components", "Systems", "Distribution",
]
INDUSTRIES = [
    "Automotive", "Aerospace", "Electronics", "Textiles", "Food Processing",
    "Construction", "Retail", "Chemicals", "Packaging", "Energy",
]
VENDOR_CATEGORIES = [
    "raw_materials", "logistics", "software", "equipment", "maintenance", "packaging",
]
FIRST_NAMES = [
    "James", "Maria", "Wei", "Fatima", "Carlos", "Aisha", "Liam", "Priya",
    "Noah", "Elena", "Kenji", "Grace", "Omar", "Sofia", "Ivan", "Chidi",
    "Anna", "Mateo", "Ling", "David",
]
LAST_NAMES = [
    "Anderson", "Garcia", "Chen", "Khan", "Rossi", "Silva", "Muller",
    "Kim", "Nguyen", "Patel", "Kowalski", "Dubois", "Ivanov", "Adeyemi",
    "Suzuki", "Brown", "Novak", "Torres", "Larsen", "Osei",
]
PRODUCT_CATALOG: dict[str, list[str]] = {
    "Industrial Equipment": ["Industrial Pump", "Hydraulic Press", "Conveyor Motor"],
    "Raw Materials": ["Steel Sheet", "Aluminum Rod", "Copper Wire Coil"],
    "Services": ["Maintenance Service", "Installation Service", "Consulting Retainer"],
    "Software": ["ERP License", "Analytics Suite License", "Support Subscription"],
    "Packaging": ["Corrugated Box Pallet", "Shrink Wrap Roll", "Pallet Wrap"],
}
DEPARTMENT_NAMES = ["Finance", "Procurement", "Operations", "Sales", "Engineering"]
EMPLOYEE_ROLES = ["Accountant", "Buyer", "Operations Manager", "Sales Rep", "Engineer"]
EXPENSE_CATEGORIES = ["travel", "meals", "supplies", "software", "training"]

# --- Simulator v2 pools (PRD Ch.19). Only consumed by the v2 phase; the v1
# pools above must never change (the frozen v1 RNG stream draws from them). ---
V2_DEPARTMENT_NAMES = ["Human Resources", "IT"]
V2_EMPLOYEE_ROLES = [
    "HR Specialist", "IT Administrator", "Financial Analyst", "Payroll Officer",
    "Procurement Analyst", "Production Planner", "Account Executive", "QA Engineer",
]
ASSET_NAME_POOLS: dict[str, list[str]] = {
    "machinery": [
        "CNC Milling Machine", "Injection Molding Press", "Welding Robot Cell",
        "Overhead Crane", "Industrial Compressor", "Packaging Line", "Lathe Station",
    ],
    "vehicle": ["Delivery Truck", "Forklift", "Company Van", "Flatbed Trailer"],
    "it_equipment": [
        "Rack Server", "Engineering Workstation", "Network Switch Stack",
        "Laptop Fleet Batch", "NAS Storage Array", "Conference AV System",
    ],
    "office_furniture": [
        "Desk Cluster", "Ergonomic Chair Set", "Meeting Room Fit-out", "Filing Cabinet Row",
    ],
}
REQUISITION_JUSTIFICATIONS = [
    "Replacement of worn production tooling",
    "Capacity expansion for the new contract",
    "Scheduled maintenance materials",
    "Department software licence renewal",
    "Safety equipment replenishment",
    "Prototype materials for engineering trial",
    "Warehouse racking extension",
    "Customer order fulfilment materials",
]
CLOSE_TASK_TEMPLATE = [
    # (task name, category)
    ("Bank reconciliation", "cash"),
    ("AR subledger reconciliation", "receivables"),
    ("AP subledger reconciliation", "payables"),
    ("Post payroll journal", "payroll"),
    ("Run depreciation", "assets"),
    ("Accrue unbilled expenses", "accruals"),
    ("Budget variance review", "reporting"),
    ("Management reporting pack", "reporting"),
]
BANK_NAMES = ["First Meridian Bank", "Commerce Trust Bank", "Northgate National Bank"]
