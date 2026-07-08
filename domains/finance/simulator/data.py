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
