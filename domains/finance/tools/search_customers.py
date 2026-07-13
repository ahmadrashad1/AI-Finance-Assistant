from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository


class SearchCustomersParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_query: str


class CustomerMatch(BaseModel):
    customer_code: str
    customer_name: str


class SearchCustomersResult(BaseModel):
    matches: list[CustomerMatch]


async def search_customers_handler(
    params: SearchCustomersParams, context: ToolContext
) -> SearchCustomersResult:
    repository = CustomerRepository(context.db)
    customers = await repository.search_by_name(params.name_query)
    return SearchCustomersResult(
        matches=[
            CustomerMatch(customer_code=customer.customer_code, customer_name=customer.company_name)
            for customer in customers
        ]
    )


SEARCH_CUSTOMERS_TOOL = ToolSpec(
    name="search_customers",
    description=(
        "Searches for customers by a partial or fragment company name "
        "(case-insensitive substring match) and returns every matching "
        "company's name and business code - zero, one, or many. Use this "
        "when the user references a customer by a short or partial name "
        "that could plausibly match more than one real company (e.g. "
        "'ABC' rather than a full company name like 'ABC Industries') - "
        "if the result has more than one match, ask the user which "
        "company they meant before doing anything else, naming the real "
        "candidates. If the user already gave what looks like a full, "
        "specific company name, use get_customer or get_customer_balance "
        "directly instead - don't use this tool for names that are "
        "already unambiguous."
    ),
    parameters_model=SearchCustomersParams,
    result_model=SearchCustomersResult,
    handler=search_customers_handler,
)
