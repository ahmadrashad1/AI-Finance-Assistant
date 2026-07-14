
## Demo: Varied phrasings route to the same tool
*PRD criterion: Understands natural English*

**User:** Show unpaid invoices.

**Assistant:** Here is the list of unpaid invoices:

| **invoice_number** | **customer_name**                | **issue_date** | **due_date** |   **total** |   **balance** | **days_outstanding** | **status** |
| -------------------- | -------------------------------- | -------------- | ------------ | ----------- | ------------ | -------------------- | ---------- |
| INV-7051             | Granite Systems                  | 2025-01-28     | 2025-03-14   |  $21,060.00 |  $21,060.00 |                     487 | overdue    |
| INV-7014             | Anchor Components                | 2025-02-23     | 2025-03-25   |  $6,534.00  |  $6,534.00  |                     476 | overdue    |
| INV-7154             | Anchor Components                | 2025-03-01     | 2025-03-31   | $72,063.00  | $72,063.00  |                     470 | overdue    |
| INV-7163             | Summit Systems                    | 2025-03-04     | 2025-04-03   | $63,234.00  | $63,234.00  |                     467 | overdue    |
| INV-7084             | Titan Components                  | 2025-03-11     | 2025-04-25   |  $7,047.00  |  $7,047.00 |                     445 | overdue    |
| INV-7054             | Summit Manufacturing               | 2025-03-01     | 2025-04-30   | $13,986.00  |  $4,195.80  |                     440 | overdue    |
| INV-7050             | Delta Logistics                   | 2025-04-01     | 2025-05-01   | $56,106.00  | $56,106.00  |                     439 | overdue    |
| INV-7080             | Atlas Manufacturing               | 2025-04-10     | 2025-05-10   | $43,200.00  | $43,200.00  |                     430 | overdue    |
| INV-7056             | Cascade Logistics                 | 2025-04-25     | 2025-05-10   | $42,714.00  |  $29,899.80 |                     430 | overdue    |
| INV-7075             | Redwood Manufacturing             | 2025-05-04     | 2025-05-19   | $11,745.00  | $11,745.00  |                     421 | overdue    |

**Total unpaid invoices: 80**
**Total amount outstanding: $2,506,110.30**
Note: This result is truncated to show the top 10 invoices by total amount outstanding. 70 invoices were omitted.

> **Trace evidence:**
> ```json
> {
>   "request_id": "ccf237df-55d5-48ce-a751-8aae136a274d",
>   "conversation_id": "69aa4950-e81d-4bba-8999-283dbbd828a1",
>   "plan": {
>     "tool_calls": [
>       {
>         "tool": "get_overdue_invoices",
>         "parameters": {}
>       }
>     ],
>     "direct_answer": null,
>     "clarification_needed": null,
>     "out_of_scope_refusal": null
>   },
>   "planning_prompt_version": "1.4.0",
>   "system_prompt_version": "1.5.0",
>   "total_duration_ms": 1289,
>   "tool_executions": [
>     {
>       "tool": "get_overdue_invoices",
>       "parameters": {},
>       "status": "success",
>       "duration_ms": 5,
>       "error_message": null
>     }
>   ]
> }
> ```

**User:** Which customers haven't paid us?

**Assistant:** I'm not able to provide the list of unpaid invoices. Unfortunately, the tool results indicate an error occurred during the request, so I don't have the necessary data.

> **Trace evidence:**
> ```json
> {
>   "request_id": "4394d760-cd63-4f5e-8d76-1c6f08beaecc",
>   "conversation_id": "a0889ac2-b674-4ab5-893a-55cd874c6e19",
>   "plan": {
>     "tool_calls": [
>       {
>         "tool": "get_unpaid_invoices",
>         "parameters": {
>           "status": "sent",
>           "minimum_amount": null
>         }
>       }
>     ],
>     "direct_answer": null,
>     "clarification_needed": null,
>     "out_of_scope_refusal": null
>   },
>   "planning_prompt_version": "1.4.0",
>   "system_prompt_version": "1.5.0",
>   "total_duration_ms": 52894,
>   "tool_executions": [
>     {
>       "tool": "get_unpaid_invoices",
>       "parameters": {
>         "status": "sent",
>         "minimum_amount": null
>       },
>       "status": "error",
>       "duration_ms": 5,
>       "error_message": "Invalid parameters for tool 'get_unpaid_invoices': 1 validation error for GetUnpaidInvoicesParams\nstatus\n  Extra inputs are not permitted [type=extra_forbidden, input_value='sent', input_type=str]\n    For further information visit https://errors.pydantic.dev/2.13/v/extra_forbidden"
>     }
>   ]
> }
> ```

**User:** Outstanding invoices?

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> **Trace evidence:**
> ```json
> {
>   "request_id": "a03860c1-0d47-4b4c-84c5-34276c4c3903",
>   "conversation_id": "87fe12ba-c224-49ca-871f-7e5e1558faa9",
>   "plan": {
>     "tool_calls": [
>       {
>         "tool": "get_unpaid_invoices",
>         "parameters": {
>           "minimum_amount": 0.0
>         }
>       }
>     ],
>     "direct_answer": null,
>     "clarification_needed": null,
>     "out_of_scope_refusal": null
>   },
>   "planning_prompt_version": "1.4.0",
>   "system_prompt_version": "1.5.0",
>   "total_duration_ms": null,
>   "tool_executions": [
>     {
>       "tool": "get_unpaid_invoices",
>       "parameters": {
>         "minimum_amount": 0.0
>       },
>       "status": "success",
>       "duration_ms": 11,
>       "error_message": null
>     }
>   ]
> }
> ```


## Demo: Multi-turn context retention
*PRD criterion: Holds multi-turn conversations and remembers context*

**User:** Show me invoices for Anchor Components

**Assistant:** Here are the invoices for Anchor Components:

**Invoices for Anchor Components**
| Invoice Number | Customer Name | Issue Date | Due Date | Total | Balance | Days Outstanding | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| INV-7014 | Anchor Components | 2025-02-23 | 2025-03-25 | 6534.00 | 6534.00 | 476 | overdue |
| INV-7154 | Anchor Components | 2025-03-01 | 2025-03-31 | 72063.00 | 72063.00 | 470 | overdue |
| **_truncated**: true, 5 out of 8 records shown. Summary: Total of 8 invoices with a total amount of $274,617.00**
| INV-7148 | Anchor Components | 2025-05-22 | 2025-06-21 | 42039.00 | 42039.00 | 388 | overdue |
| INV-7059 | Anchor Components | 2025-08-19 | 2025-09-18 | 49221.00 | 24610.50 | 299 | overdue |
| INV-7135 | Anchor Components | 2026-03-05 | 2026-04-04 | 43200.00 | 43200.00 | 101 | overdue |

Note: I've only shown the top records (by materiality or urgency) out of the total count. The true overall totals are:

- Total count: 8
- Total amount: $274,617.00

> **Trace evidence:**
> ```json
> {
>   "request_id": "9b928fc7-1392-4c98-b1bc-f627ea3b64b7",
>   "conversation_id": "cd852805-a874-4240-ab2c-f74024cb4262",
>   "plan": {
>     "tool_calls": [
>       {
>         "tool": "get_customer",
>         "parameters": {
>           "customer_name": "Anchor Components"
>         }
>       },
>       {
>         "tool": "search_invoices",
>         "parameters": {
>           "customer_id": "$step0.customer_code"
>         }
>       }
>     ],
>     "direct_answer": null,
>     "clarification_needed": null,
>     "out_of_scope_refusal": null
>   },
>   "planning_prompt_version": "1.4.0",
>   "system_prompt_version": "1.5.0",
>   "total_duration_ms": 44502,
>   "tool_executions": [
>     {
>       "tool": "get_customer",
>       "parameters": {
>         "customer_name": "Anchor Components"
>       },
>       "status": "success",
>       "duration_ms": 1,
>       "error_message": null
>     },
>     {
>       "tool": "search_invoices",
>       "parameters": {
>         "customer_id": "CUST-0003"
>       },
>       "status": "success",
>       "duration_ms": 7,
>       "error_message": null
>     }
>   ]
> }
> ```

**User:** Only the ones above $5,000

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

**User:** What's their total balance?

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable


## Demo: Tool selection and parameter extraction
*PRD criterion: Chooses the correct tools and extracts correct parameters*

**User:** Show invoices overdue by more than 60 days

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

**User:** Generate an aging report

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

**User:** Find duplicate invoices

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

**User:** What's our cash position?

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable


## Demo: Honesty under missing data
*PRD criterion: Accurate data from the simulator; zero hallucinated finance data*

**User:** Show me invoice INV-99999

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

**User:** Show me unpaid invoices over $10,000,000

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

**User:** Show me Anchor's invoices

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable


## Demo: Clear explanations and scope honesty
*PRD criterion: Explains results clearly; refuses out-of-scope actions*

**User:** Generate an aging report and explain which bucket worries you most

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

**User:** Delete all invoices

**Assistant:** [error event] The assistant is busy right now. Please try again shortly.

> trace: unavailable

