from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ai_platform.tool_registry.registry import ToolContext, ToolSpec
from domains.finance.repositories.customer_repository import CustomerRepository


class GetCustomerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str


class GetCustomerResult(BaseModel):
    customer_code: str
    customer_name: str


async def get_customer_handler(
    params: GetCustomerParams, context: ToolContext
) -> GetCustomerResult:
    repository = CustomerRepository(context.db)
    customer = await repository.get_by_name(params.customer_name)
    if customer is None:
        raise ValueError(f"Customer not found: {params.customer_name}")
    return GetCustomerResult(
        customer_code=customer.customer_code, customer_name=customer.company_name
    )


GET_CUSTOMER_TOOL = ToolSpec(
    name="get_customer",
    description=(
        "Resolves a customer's company name to their business code and "
        "confirmed name - a pure identity lookup with no balance or "
        "invoice data. Requires customer_name (the company name as the "
        "user says it, e.g. 'ABC Industries' - not a business code). Use "
        "this as the first step of a multi-step plan when a later tool "
        "call needs a customer_id (business code) but the user only gave "
        "a company name - e.g. 'Which of those belong to ABC Industries?' "
        "resolves ABC Industries to its code first, then filters the "
        "invoice tool by that code. Don't use this when the question is "
        "just about one customer's balance (use get_customer_balance "
        "directly instead)."
    ),
    parameters_model=GetCustomerParams,
    result_model=GetCustomerResult,
    handler=get_customer_handler,
)
