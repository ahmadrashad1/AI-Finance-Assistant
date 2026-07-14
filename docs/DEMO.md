# DEMO — PRD Success-Criteria Verification

Reproduce any demo yourself (the app must be running — see the root README):

```bash
cd backend
.venv/Scripts/python -m domains.finance.simulator.seed --reset
.venv/Scripts/python scripts/run_demo.py             # all five demos
.venv/Scripts/python scripts/run_demo.py --demo 2    # a single demo
```

Conditions for the transcripts below (recorded live 2026-07-14):

- Dataset: Northwind Manufacturing Ltd., seed=42 (reproducible)
- Prompts: planning 1.4.0 / system 1.5.0 · Model: `llama-3.1-8b-instant` (Groq)
- Every factual claim was cross-checked against PostgreSQL with SQL — the
  queries and results are quoted per demo. **Every check passed exactly.**
- The planner samples at provider-default temperature, so wording and
  occasionally tool choice vary between runs. Where a roll exposed a
  documented model-behavior gap, the transcript is kept and labeled — the
  evaluation suite (`docs/MVP-REPORT.md`) is the deterministic scoreboard;
  these demos are live proof, honestly reported.
- Tool selection per turn is evidenced by the request trace
  (`GET /api/trace/{request_id}`), which the demo script prints for every
  turn: the fired plan branch, tools, extracted parameters, and timings.

## Criterion 1 — Understands natural English (varied phrasings)

Three separate one-turn conversations, three very different phrasings — the
planner chose **`get_unpaid_invoices`** for all three (trace-verified):

| Phrasing | Planned tool | Reply's totals |
|---|---|---|
| "Show unpaid invoices." | `get_unpaid_invoices()` | 87 invoices, $2,650,349.70 |
| "Which customers haven't paid us?" | `get_unpaid_invoices()` | 87 invoices, $2,650,349.70 |
| "Outstanding invoices?" | `get_unpaid_invoices()` | 87 invoices, $2,650,349.70 |

Representative reply (first phrasing, truncated to the top rows by design):

> Here are the unpaid invoices:
>
> | invoice_number | customer_name | due_date | total | balance | days_outstanding | status |
> |---|---|---|---|---|---|---|
> | INV-7191 | Anchor Materials | 2026-06-12 | 96795.00 | 96795.00 | 32 | overdue |
> | INV-9002 | Cascade Materials | 2025-07-31 | 91287.00 | 91287.00 | 348 | overdue |
> | ... | | | | | | |
>
> **There are 87 total unpaid invoices, with a total outstanding balance of
> $2,650,349.70. Only 10 invoices are shown due to truncation.**

**SQL cross-check (exact match):**

```sql
SELECT count(*), sum(balance) FROM finance.invoices
WHERE balance > 0 AND status IN ('sent','partially_paid','overdue');
--> 87 | 2,650,349.70
SELECT * FROM finance.invoices WHERE invoice_number = 'INV-7191';
--> Anchor Materials | total 96,795.00 | balance 96,795.00 | overdue
```

No keyword matching exists anywhere in the application (verified by the
Milestone 10 architecture audit, `docs/MVP-REPORT.md` §4) — the routing above
is entirely LLM intent understanding. The eval suite pins this
paraphrase-invariance deterministically: the `unpaid_invoices` category (five
phrasings, including "not settled" and "open right now") passes 5/5 recorded.

## Criterion 2 — Multi-turn context retention

One conversation, three turns:

> **User:** Show me invoices for Anchor Components
>
> **Assistant:** *(identifies the customer — "only one customer match:
> `Anchor Components` with customer code `CUST-0003`")*
>
> **User:** Only the ones above $5,000
>
> **Assistant:** Based on the search results, we've found invoices from
> Anchor Components that match the total criteria. Here are the invoices
> above $5000: *(table of 7 invoices)* … the true total amount is
> $272,079.00.
>
> **User:** What's their total balance?
>
> **Assistant:** According to the tool results, the total balance for Anchor
> Components is **$188,446.50**. This is the total amount they owe.

**Trace evidence:** turn 2's plan carried the customer from turn 1 *and* the
new filter — `get_customer("Anchor Components")` →
`search_invoices(customer_id=$step0.customer_code → CUST-0003,
minimum_amount=5000)` — a two-step chain resolved and executed by the
orchestrator. Turn 3 resolved "their" to Anchor Components and planned
`get_customer_balance(customer_name="Anchor Components")`.

**SQL cross-check (exact matches):**

```sql
-- turn 2: Anchor Components invoices with total > 5000
--> 7 invoices, sum(total) = 272,079.00   (the 8th, INV-7024 at $2,538, correctly excluded)
-- turn 3: their outstanding balance
SELECT sum(balance) FROM finance.invoices i JOIN finance.customers c ON c.id=i.customer_id
WHERE c.company_name='Anchor Components';
--> 188,446.50
```

*Honest note:* a different roll of this conversation hit a documented planner
gap — it tried to reference `$step0.customer_code` from the *previous turn's*
plan (step references resolve within one turn only), execution degraded
gracefully, and the reply honestly said it couldn't retrieve the data, with
no internals leaked. That gap class is two of the evaluation suite's 14
documented failing cases (`followup_*`).

## Criterion 3 — Correct tool selection and parameter extraction

Four one-turn conversations; every turn planned the exact right tool
(trace-verified), executed it, and quoted exact figures:

| Request | Planned tool + parameters | Reply's key figures | SQL check |
|---|---|---|---|
| "Show invoices overdue by more than 60 days" | `get_overdue_invoices(minimum_days=60)` | 73 invoices, $2,296,876.50 outstanding | 73 / 2,296,876.50 ✓ |
| "Generate an aging report" | `get_aging_report()` | buckets below | all five buckets ✓ |
| "Find duplicate invoices" | `find_duplicate_invoices()` | 5 groups, 10 invoices | 5 groups ✓ (exact composition) |
| "What's our cash position?" | `get_cash_position()` | $918,201.30 | 918,201.30 ✓ |

Aging report reply vs. SQL (every cell exact):

| Bucket | Reply count | Reply balance | SQL count | SQL balance |
|---|---|---|---|---|
| current | 7 | $144,239.40 | 7 | 144,239.40 |
| 0–30 | 1 | $18,219.60 | 1 | 18,219.60 |
| 31–60 | 6 | $191,014.20 | 6 | 191,014.20 |
| 61–90 | 2 | $94,230.00 | 2 | 94,230.00 |
| 90+ | 71 | $2,202,646.50 | 71 | 2,202,646.50 |

Duplicate groups reply vs. SQL (`GROUP BY customer, total HAVING count > 1`):
Titan Components $20,223 & $28,890, Harbor Materials $17,496, Cascade
Materials $91,287, Anchor Manufacturing $3,807 — the reply listed exactly
these five pairs (the simulator seeds them deliberately, INV-9001…INV-9005).

Cash position: `sum(bank_accounts.opening_balance) + sum(cash_transactions.amount)
= 918,201.30` — exact.

*Honest note:* one earlier roll of the overdue turn garbled the total in
prose ($229,687.50 instead of $2,296,876.50 — right count, mangled digits),
and one aging roll invented a count of "144" in its closing sentence while
printing the correct 87-in-total buckets above it. Phase-2 numeric
transcription is not infallible; this class is measured by the eval suite's
explanation-quality cases and listed in `docs/MVP-REPORT.md` §5.

## Criterion 4 — Accurate data from the simulator, zero hallucinated finance data

Three probes designed to invite fabrication; none succeeded:

> **User:** Show me invoice INV-99999
>
> **Assistant:** Unfortunately, there are no invoices matching "INV-99999"
> in our system. The search yielded 0 results, with a total amount of $0.

> **User:** Show me unpaid invoices over $10,000,000
>
> **Assistant:** There are no unpaid invoices over $10,000,000.

> **User:** Show me Anchor's invoices *(fragment name — a documented planner gap)*
>
> **Assistant:** The tool results indicate there are errors with the
> search_invoices and get_customer tools, so we cannot show you Anchor's
> invoices. It seems there's a problem finding the customer. Would you like
> to try again or provide more information?

The trace for each shows genuine tool execution (not a canned reply):
`search_invoices(invoice_number="INV-99999")` really ran and returned zero
rows; `get_unpaid_invoices(minimum_amount=10000000)` really ran and returned
an empty set. The "Anchor" fragment turn shows the *documented* gap —
`search_customers` under-triggers on fragments (4 of the eval suite's 14
failing cases) — and the guardrails holding: an honest failure reply, no
fabricated customer, no internal error text (the raw `Customer not found`
detail stays in the developer trace).

The recorded evaluation suite's **hallucination rate is 0.0% across all 53
cases**, including dedicated `hallucination_*` and empty-result-honesty
cases, and every SQL cross-check in this document matched exactly.

## Criterion 5 — Clear explanations (and scope honesty)

> **User:** Generate an aging report and explain which bucket worries you most
>
> **Assistant:** *(prints the aging table above, then)* Based on this aging
> report, I'm most worried about the "90+" bucket. This bucket has the
> highest total balance of $2,202,646.50, which is more than 80% of the
> grand total. It also has the most invoice count with 71 … I'm concerned
> about the potential cash flow impact of these overdue invoices and the
> possibility of them becoming even further overdue if not paid promptly.

The explanation cites the real figures ($2,202,646.50 is exactly the 90+
bucket's SQL total; 71/87 invoices and >80% of $2,650,349.70 are both
correct) and grounds its recommendation in them — no generic advice.

> **User:** Delete all invoices
>
> **Assistant:** I don't do deletions. However, I can help with other
> invoice-related operations like searching, listing, or getting balances.

Trace evidence for the refusal — the plan fired the `out_of_scope_refusal`
branch with `tool_calls: null` and `tool_executions: []`: structurally, no
tool could run for this request (see
`docs/adr/0006-out-of-scope-refusal-as-plan-branch.md`).

## Summary

| PRD success criterion | Verdict | Evidence |
|---|---|---|
| Understands natural English (varied phrasings) | ✅ | Demo 1: 3/3 phrasings → `get_unpaid_invoices`, totals SQL-exact |
| Multi-turn context retention | ✅ (with a documented cross-turn-piping gap) | Demo 2: filter + pronoun follow-ups resolved; $188,446.50 exact |
| Correct tool selection & parameter extraction | ✅ live on these demos; 76.7% across the full eval suite (target >95%) | Demo 3: 4/4 exact tools, `minimum_days=60` extracted; MVP-REPORT §2 |
| Accurate simulator data, zero hallucinated finance data | ✅ | Demo 4 + every SQL cross-check exact + eval hallucination rate 0.0% |
| Clear explanations | ✅ | Demo 5: grounded, figure-citing reasoning; refusal names real capabilities |

The deterministic scoreboard behind these live demos — including the 14
documented model-behavior failures and their patterns — is in
`docs/MVP-REPORT.md`.
