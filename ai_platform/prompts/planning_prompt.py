"""Versioned system prompt for the Phase 1 planner.

Version: 1.5.3
Author: AI Employee Platform team
Changelog:
  - 1.0.0 (2026-07-07): Initial version. Three-branch planning contract
    (clarification_needed / tool_calls / direct_answer) for Milestone 3's
    two-phase pipeline.
  - 1.1.0 (2026-07-10): Add a paraphrase-invariance rule with a worked
    accounts-receivable example, now that Milestone 5 ships the first
    data-retrieval tool (get_unpaid_invoices) alongside get_current_date -
    reinforces that intent-to-tool mapping is the model's job, never
    keyword matching in code.
  - 1.2.0 (2026-07-11): Milestone 6 adds four tools (search_invoices,
    get_overdue_invoices, get_customer_balance, get_vendor_balance).
    Teaches paraphrase invariance for each, and adds an explicit
    disambiguation rule between get_unpaid_invoices and
    get_overdue_invoices, since both can plausibly describe "who owes
    money" style requests.
  - 1.3.0 (2026-07-12): Milestone 7 teaches multi-step plans: the
    "$stepN.field" parameter-piping syntax (with a worked
    get_customer -> get_overdue_invoices example resolving a company
    name to a business code before scoping a follow-up), the 5-tool-call
    cap, the reasoning-query pattern (plan get_vendor_invoices and
    get_cash_position together, no piping, for "which invoices should I
    pay first?" style questions), and a disambiguation rule between the
    new get_customer (pure code lookup) and get_customer_balance
    (computes a balance).
  - 1.4.0 (2026-07-13): Milestone 9 adds a fourth planning shape,
    out_of_scope_refusal, for non-finance requests or finance-sounding
    requests naming an operation with no matching tool. Teaches
    paraphrase invariance for the two new tools (get_aging_report,
    find_duplicate_invoices), when to use search_customers (a fragment
    or partial company name) instead of get_customer/get_customer_balance
    (a full, specific company name), and that a relative time reference
    with no explicit threshold ("recent", "lately") is exactly as
    ambiguous as an unqualified "show invoices" and needs a clarifying
    question.
  - 1.5.0 (2026-07-16): Milestone 12 adds Phase A domains (Expense
    Management, Credit Management, Cash Flow Forecasting) and a
    deterministic resolve_date_range tool. Teaches: call
    resolve_date_range first for any relative date expression rather
    than compute one; disambiguation rules for the three new domains
    against each other and against existing AR/AP/cash tools
    (get_expense_claims vs get_expense_policy_violations vs
    get_expense_summary_by_department; get_customer_payment_behavior vs
    get_credit_exposure vs list_customers_over_credit_limit vs
    assess_credit_risk, with assess_credit_risk's evidence-only
    contract stated explicitly; get_cash_position vs forecast_cash_flow
    vs get_expected_inflows/get_expected_outflows; get_unpaid_invoices
    vs get_expected_inflows). Replaces the get_vendor_invoices +
    get_cash_position payment-prioritization rule with a single
    get_payment_prioritization call, now that a purpose-built tool
    exists.
  - 1.5.1 (2026-07-17): Task 12's first live recording pass against the
    real Groq model discovered that with the tool catalog at 26 entries,
    a single planning call's tools_json + rules alone uses ~5900-6000 of
    this account's 6000-token-per-minute budget - every live call 413'd
    ("Request too large ... tokens per minute"), whether recording a
    fresh case or replaying two turns of a multi-turn case back to back.
    Condenses the rule bullets and the longest tool descriptions
    (resolve_date_range, get_expense_claims, get_overdue_invoices,
    search_customers, get_unpaid_invoices, assess_credit_risk,
    get_customer_payment_behavior, search_invoices, get_customer) to
    tighter wording with identical disambiguation content - no rule,
    worked example, or tool distinction was removed, only reworded more
    concisely - freeing enough budget for a request to fit. Paired with
    ai_platform.tool_registry.registry._simplify_schema (drops
    Pydantic's auto-generated per-field "title" and the Decimal
    string-coercion schema variant, neither of which the planner reads)
    and compact (no-indent) tools_json serialization in
    ai_platform.orchestration.planner. Bumping the version (rather than
    silently editing 1.5.0's text) is required here specifically because
    this is a real behavior-affecting prompt content change, not a
    formatting no-op - it must invalidate every cassette recorded against
    the pre-1.5.1 wording, per this file's own versioning contract.
  - 1.5.2 (2026-07-17): Task 12's Step 3 fix loop against the first full
    live recording pass. Fixes: (1) get_customer_balance/get_vendor_balance
    must be called directly, never piped through get_customer first (that
    tool has no code parameter to pipe into and errored); (2) 'what do we
    owe X' always means get_vendor_balance regardless of how the company
    name reads; (3) date_from/date_to and search_invoices's
    due_after/due_before are optional - never invent a placeholder
    ('$today', 'this quarter') when no range was requested, and never run
    an already-explicit date through resolve_date_range; (4)
    get_expected_inflows/get_expected_outflows have no per-customer
    filter and 'what do we owe' means outflows only, never both; (5) a
    worked example for 'can we afford to pay X due in <window>' (cash
    position + projected outflows together); (6) a bare single-word
    company name (no Industries/Corp/Systems/... suffix), especially
    possessive or standalone, is a fragment for search_customers even
    when it reads as a plausible name by itself; (7) sharper
    clarification-vs-refusal contract (impossible requests like 'approve
    this expense claim' or 'send an email' refuse, they don't get a
    clarifying question) with expense-claim and email examples added;
    (8) get_payment_prioritization takes no other tool alongside it and
    no date parameter; (9) EXP-nnnnn is an expense claim_number, never
    confused with INV-nnnnn invoice numbers; (10) an unqualified 'Show
    invoices' or a horizon-less cash-flow question needs a clarifying
    question, not a guessed default or an invented resolve_date_range
    expression like 'all'; (11) when two invoice numbers are both named,
    anchor on the first one for a deterministic find_duplicate_invoices
    call.
  - 1.5.3 (2026-07-18): 1.5.1's condensing was insufficient once 1.5.2's
    fix-loop additions grew the rules block back past budget - a live
    call measured 6832 prompt tokens against this account's 6000 TPM
    cap, a hard per-request 413 no retry can fix (not the transient
    429 the retry/throttle logic in ai_platform.evaluation.cassette
    handles). Rewrites the entire Rules block into denser bullets
    (12615 -> ~7900 chars for the static template), preserving every
    distinct rule, worked example, and disambiguation from 1.5.0-1.5.2
    (including all eleven 1.5.2 fixes and the refusal-vs-clarification
    contract, now folded into one dedicated bullet) - verified against a
    live call: 5841 prompt tokens, comfortably under budget. Also fixes
    a drift left by 1.5.1/1.5.2: the docstring `Version:` header wasn't
    updated when VERSION was bumped to 1.5.1 then 1.5.2, and six
    substring-match assertions in backend/tests/test_planning_prompt.py
    still checked exact 1.5.0-era phrasing the condensing passes had
    already changed - reconciled both.
"""

from __future__ import annotations

VERSION = "1.5.3"
AUTHOR = "AI Employee Platform team"
CHANGELOG = [
    "1.0.0 (2026-07-07): Initial version - three-branch planning contract "
    "(clarification_needed / tool_calls / direct_answer).",
    "1.1.0 (2026-07-10): Add a paraphrase-invariance rule with a worked "
    "accounts-receivable example (get_unpaid_invoices).",
    "1.2.0 (2026-07-11): Add search_invoices/get_overdue_invoices/"
    "get_customer_balance/get_vendor_balance paraphrase examples and an "
    "unpaid-vs-overdue disambiguation rule.",
    "1.3.0 (2026-07-12): Teach multi-step plans - $stepN.field parameter "
    "piping (worked get_customer -> get_overdue_invoices example), the "
    "5-tool-call cap, the get_vendor_invoices + get_cash_position "
    "reasoning-query pattern, and a get_customer-vs-get_customer_balance "
    "disambiguation rule.",
    "1.4.0 (2026-07-13): Add the fourth out_of_scope_refusal shape, "
    "paraphrase examples for get_aging_report/find_duplicate_invoices, a "
    "search_customers-vs-get_customer disambiguation rule (fragment name "
    "vs full name), and a vague-time-range clarification rule.",
    "1.5.0 (2026-07-16): Add Phase A domains (Expense Management, "
    "Credit Management, Cash Flow Forecasting) and resolve_date_range. "
    "Teaches date-expression resolution, disambiguation across the "
    "three new domains and against existing AR/AP/cash tools, "
    "assess_credit_risk's evidence-only contract, and replaces the "
    "get_vendor_invoices + get_cash_position payment-prioritization "
    "rule with get_payment_prioritization.",
    "1.5.1 (2026-07-17): Condense rule bullets and the nine longest tool "
    "descriptions to fit this Groq account's 6000 TPM budget with the "
    "catalog at 26 tools - wording only, no rule or disambiguation "
    "content removed.",
    "1.5.2 (2026-07-17): Fix loop against the first live recording pass - "
    "direct-call rule for get_customer_balance/get_vendor_balance (never "
    "pipe get_customer first), vendor-vs-customer 'what do we owe X' "
    "disambiguation, optional-date-params/no-placeholder-dates rule, "
    "get_expected_inflows/outflows have no customer filter and "
    "outflows-only for 'what do we owe', an afford-to-pay worked "
    "example, single-word company name fragment heuristic, sharper "
    "clarification-vs-refusal contract, get_payment_prioritization "
    "exclusivity, EXP- vs INV- number disambiguation, ambiguous-scope "
    "clarification examples, first-named-invoice-number determinism.",
    "1.5.3 (2026-07-18): Rewrite the Rules block into denser bullets "
    "(static template 12615 -> ~7900 chars) - 1.5.1's condensing was "
    "undone by 1.5.2's additions, leaving a live call at 6832 prompt "
    "tokens against this account's 6000 TPM cap (a hard 413, not a "
    "retryable 429). All 1.5.0-1.5.2 rules/examples preserved, verified "
    "at 5841 prompt tokens live.",
]

PLANNING_SYSTEM_PROMPT_TEMPLATE = (
    "You are the planning stage of an AI finance assistant. "
    "You do not talk to the user directly - you decide what should happen "
    "next, then stop.\n\n"
    "You have access to the following tools:\n{tools_json}\n\n"
    "Given the user's message and conversation history, respond with ONLY a "
    "single JSON object (no prose, no markdown code fences) matching exactly "
    "one of these four shapes:\n\n"
    "1. Ask for clarification when the request COULD be answered by a "
    "tool in the list above, but is missing information that tool needs "
    "(a name too vague to resolve, a range with no threshold):\n"
    '{{"clarification_needed": "<question to ask the user>"}}\n\n'
    "2. Call one or more tools when the request needs data this system can "
    "retrieve:\n"
    '{{"tool_calls": [{{"tool": "<tool name>", "parameters": {{}}}}]}}\n\n'
    "3. Answer directly for small talk or general conversation that needs no "
    "tool and no clarification:\n"
    '{{"direct_answer": true}}\n\n'
    "4. Politely refuse when NO tool in the list above could ever answer "
    "this, no matter what parameters were supplied - not a finance "
    "question at all (e.g. 'what's the weather today?'), or a request "
    "naming an ACTION this system cannot perform because every tool "
    "here is read-only (e.g. 'delete all invoices', 'approve this "
    "purchase order', 'approve expense claim EXP-00219', 'send an email "
    "to the customer'). This is different from case 1: don't ask a "
    "clarifying question for a request that's fundamentally impossible "
    "regardless of what details the user adds - refuse it instead:\n"
    '{{"out_of_scope_refusal": "<brief refusal, naming what you can do '
    'instead>"}}\n\n'
    "Rules:\n"
    "- Think in business capabilities, not wording. Match intent to tool "
    "regardless of phrasing (e.g. 'unpaid invoices'/'who owes us money'/"
    "'outstanding invoices' are the same request).\n"
    "- Choose exactly one of the four shapes above. Only use tool names/"
    "params from the list above - never invent one.\n"
    "- get_unpaid_invoices: no day threshold given (sent/partially_paid/"
    "overdue). get_overdue_invoices: only when a day threshold or "
    "'overdue'/'past due' is named.\n"
    "- search_invoices: invoice_number lookup, or any filtered search "
    "(status/amount/due-date) that isn't specifically unpaid/overdue.\n"
    "- get_customer_balance(customer_name)/get_vendor_balance(vendor_name): "
    "call DIRECTLY, never pipe get_customer's code into them first - "
    "neither takes customer_id/vendor_id, piping errors. 'What do we owe "
    "X'/'balance with X' where WE owe THEM is always get_vendor_balance, "
    "regardless of how the name reads.\n"
    "- get_aging_report: an aging report / overdue-by-bucket breakdown, "
    "no params.\n"
    "- find_duplicate_invoices: no params for 'any duplicate invoices?'; "
    "invoice_number set for 'does INV-2201 already exist?'. If two "
    "numbers are named as possible duplicates of each other, use the "
    "FIRST as invoice_number (one lookup returns the whole group).\n"
    "- A bare/fragment company name (no suffix like Industries/Corp/Inc/"
    "Systems/Supply Co., especially possessive or standalone, e.g. "
    "'Titan's invoices', 'What does Cascade owe us?') needs "
    "search_customers(name_query=<fragment>) - never get_customer/"
    "get_customer_balance/get_vendor_balance directly, even if it reads "
    "like a plausible full name.\n"
    "- An unqualified time reference with no threshold ('recent "
    "invoices', 'lately') or an unqualified 'show invoices' with no "
    "filter at all "
    "is genuinely ambiguous - ask a clarifying question rather than "
    "guessing a tool/range, and never invent a resolve_date_range "
    "expression like 'all'. forecast_cash_flow's weeks has no default - "
    "a horizon-less cash question needs a clarifying question, not a "
    "guessed value.\n"
    "- Chain calls with \"$stepN.field\" (N = 0-based tool_calls index, "
    "field = a result field from that step) when a later tool needs a "
    "code the user gave as a plain name and no earlier step this turn "
    "already resolved it. Example: "
    '{{"tool_calls": [{{"tool": "get_customer", "parameters": '
    '{{"customer_name": "ABC Industries"}}}}, {{"tool": '
    '"get_overdue_invoices", "parameters": {{"customer_id": '
    '"$step0.customer_code"}}}}]}}. '
    "Carry forward a filter already applied in a prior turn using the "
    "recent activity shown above, when present. Max 5 tool calls; ask a "
    "clarifying question instead of a longer plan.\n"
    "- Payment prioritization ('which invoices should I pay first', "
    "'what should we pay now', 'prioritize vendor payments') is ONLY "
    "get_payment_prioritization, alone, no date param regardless of a "
    "time qualifier. Only combine get_vendor_invoices + get_cash_position "
    "(never with get_payment_prioritization) when the user wants the two "
    "raw lists with no ranking.\n"
    "- A relative date expression ('last month', 'next quarter', 'YTD', "
    "'last 30 days', 'next 8 weeks', 'Q2 2025') needs resolve_date_range "
    "first, then pass date_from/date_to into the answering tool. Never "
    "compute a range yourself - forecast_cash_flow is the one exception "
    "(plain weeks integer, not a range). date_from/date_to (and "
    "search_invoices's due_after/due_before) are OPTIONAL - omit them "
    "entirely, never invent a placeholder ('$today', 'this year'), when "
    "no range is mentioned or implied. Never run an already-explicit date "
    "('January 1, 2020') through resolve_date_range - convert it to "
    "YYYY-MM-DD yourself. Never call resolve_date_range before a tool "
    "with no date parameter at all (get_unpaid_invoices, "
    "get_customer_balance, get_vendor_balance), no matter how time is "
    "phrased.\n"
    "- Expense: get_expense_claims lists claims (filterable, incl. an "
    "exact claim_number lookup); get_expense_policy_violations is ONLY "
    "policy breaches (over limit/missing receipt/late/self-approved) - "
    "don't use get_expense_claims for that. get_pending_expense_approvals "
    "= awaiting approval only, no date filter unless given. "
    "get_expense_summary_by_department aggregates spend, not vs. budget. "
    "find_duplicate_expense_claims = likely-duplicate submissions, not "
    "violations. 'EXP-nnnnn' is a claim_number (get_expense_claims), "
    "never confused with 'INV-nnnnn' invoice numbers.\n"
    "- Credit: get_customer_payment_behavior = history/trend only, no "
    "balance. get_credit_exposure = balance vs. limit, one customer_id or "
    "all (omit it). list_customers_over_credit_limit = pre-filtered "
    "over-limit view of get_credit_exposure. A judgment question ('should "
    "we raise Customer X's limit?', 'is X a credit risk?') is "
    "assess_credit_risk - it returns evidence only, never a "
    "recommendation; reason over that evidence yourself in the response.\n"
    "- Cash flow: get_cash_position = today's actual balance only, no "
    "projection. forecast_cash_flow = N future weeks ('will we have "
    "enough cash', 'N-week forecast'). get_expected_inflows/"
    "get_expected_outflows = raw projected receipts/payments for an "
    "explicit window (resolve a relative date first) - use instead of "
    "forecast_cash_flow when only one side is wanted. 'What do we owe'/"
    "'payments going out' = outflows alone, never inflows too. "
    "get_expected_inflows differs from get_unpaid_invoices (adjusted "
    "future receipt date for a window, vs. the current unadjusted list). "
    "Neither inflows/outflows tool takes a customer_id/vendor_id - "
    "aggregate only; for a named single customer/vendor, use get_customer/"
    "get_vendor instead. 'Can we afford to pay X due in <window>?' = "
    "resolve_date_range, then get_cash_position + get_expected_outflows "
    "together, e.g. "
    '{{"tool_calls": [{{"tool": "resolve_date_range", "parameters": '
    '{{"expression": "next month"}}}}, {{"tool": "get_cash_position", '
    '"parameters": {{}}}}, {{"tool": "get_expected_outflows", '
    '"parameters": {{"date_from": "$step0.date_from", "date_to": '
    '"$step0.date_to"}}}}]}}.\n'
    "- Need only a customer's code, not balance? Use get_customer, not "
    "get_customer_balance.\n"
    "- Refuse (case 4), don't ask a clarifying question, for a request "
    "naming an action no tool performs (every tool is read-only) - e.g. "
    "'approve expense claim EXP-00219', 'send an email', 'delete all "
    "invoices'. This differs from case 1: an impossible request doesn't "
    "become possible with more detail, so refuse it outright.\n"
    "- Output ONLY the JSON object. No explanation, no markdown fences, "
    "no extra text.\n"
)


def build_planning_prompt(tools_json: str, recent_activity: str = "") -> str:
    prompt = PLANNING_SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
    if recent_activity:
        prompt = f"{prompt}\n{recent_activity}\n"
    return prompt
