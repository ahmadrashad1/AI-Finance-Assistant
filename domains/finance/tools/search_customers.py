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
        "Searches customers by a partial/fragment company name "
        "(case-insensitive substring match), returning every match's "
        "name and business code - zero, one, or many. Use when the user "
        "gives a short or partial name that could match more than one "
        "company (e.g. 'ABC' vs 'ABC Industries') - if more than one "
        "match, ask which company they meant, naming the candidates. If "
        "the name already looks full and specific, use get_customer or "
        "get_customer_balance directly instead."
    ),
    parameters_model=SearchCustomersParams,
    result_model=SearchCustomersResult,
    handler=search_customers_handler,
)
