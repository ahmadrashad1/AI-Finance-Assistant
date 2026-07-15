AI Finance Assistant MVP
Product Requirements Document (PRD) & Software Design Document (SDD)

Version: 1.0

Status: Draft

Primary Goal:

Build an AI Finance Assistant that works flawlessly on localhost using a Finance Simulation Environment before integrating with any real ERP systems or deploying to production.

Chapter 1 — Executive Summary
Overview

The AI Finance Assistant is an intelligent conversational application designed to assist finance employees with repetitive daily tasks.

Unlike traditional ERP systems that require users to navigate complex interfaces and reports, the AI Finance Assistant allows finance employees to interact using natural language.

Instead of clicking through dashboards, users simply ask questions such as:

Which customers haven't paid us?

or

Show invoices overdue by more than 60 days.

or

Find duplicate invoices.

The assistant understands the request, reasons about the user's intent, selects the appropriate finance tools, retrieves the required information, and responds in natural English.

The long-term vision is to integrate with enterprise finance systems such as SAP, Oracle, Microsoft Dynamics, ERPNext, or Odoo.

However,

this MVP intentionally avoids all production integrations.

Instead, a realistic Finance Simulation Environment will be developed to validate the complete AI workflow.

Primary Objective

The objective of this MVP is NOT to build a production SaaS platform.

The objective is NOT to integrate with real ERP systems.

The objective is NOT to solve cloud deployment.

The objective is ONLY to answer the following question:

Can we build an AI Finance Assistant that consistently understands finance-related questions, chooses the correct finance tools, reasons correctly, and returns accurate responses?

Everything else is postponed.

Success Criteria

The MVP will be considered successful if the assistant can:

✅ Understand natural English

✅ Hold multi-turn conversations

✅ Remember previous context

✅ Choose the correct finance tools

✅ Correctly extract parameters

✅ Query the Finance Simulator

✅ Reason over returned data

✅ Produce accurate responses

✅ Pass automated evaluation tests

Target Users

The first version is designed for finance professionals.

Examples include:

Accounts Payable Clerks
Accounts Receivable Clerks
Finance Managers
Controllers
CFOs (for reporting queries)

No technical knowledge should be required.

Users should feel like they are talking to an experienced finance colleague.

Core Philosophy

The AI Finance Assistant is not a chatbot in the traditional sense.

It is an AI-powered reasoning system.

Conversation is simply the interface.

Internally, the assistant:

Understands intent.
Chooses the correct tools.
Retrieves structured finance data.
Reasons over that data.
Produces an accurate answer.
Chapter 2 — Vision & Product Philosophy
Traditional ERP Software

Today's finance systems require users to:

navigate multiple menus
remember report names
search across several modules
export spreadsheets
manually compare information

These systems expose software functionality.

AI Finance Assistant

The AI Finance Assistant exposes business capabilities, not software functionality.

Instead of asking users to learn the software,

the software learns how users naturally speak.

For example,

instead of:

Finance → Reports → Accounts Receivable → Aging Report

the user simply types:

Which customers owe us the most money?

The assistant should understand this immediately.

Conversation First

The product should feel like ChatGPT.

Users should never think about:

commands
keywords
syntax
filters
SQL
APIs

Instead,

they should simply ask questions naturally.

Natural Language First

The assistant must NEVER rely on keywords.

Example:

All of these should produce the same internal tool call:

Show unpaid invoices.

Which invoices haven't been paid?

Outstanding invoices?

Who still owes us money?

Customers with overdue invoices.

Internally,

the AI determines that all of these requests correspond to:

get_unpaid_invoices()

No keyword matching should exist anywhere in the application.

Natural language understanding is a fundamental requirement.

The Assistant Must Behave Like a Human Finance Employee

Imagine hiring a junior accountant.

You wouldn't expect them to memorize command syntax.

Instead,

you would expect them to understand requests like:

Can you remind customers who are more than 30 days overdue?

Our assistant should behave exactly the same way.

AI Before Automation

The purpose of the assistant is NOT automation.

Automation may happen later.

The assistant's first responsibility is reasoning.

Reasoning always comes before execution.

For example,

if the user asks:

Which invoices should I pay first?

There is no single finance tool for this.

Instead,

the assistant should:

retrieve unpaid invoices
retrieve payment terms
retrieve due dates
retrieve available cash
apply company policy
reason
produce recommendations

This is fundamentally different from rule-based automation.

Localhost First

The entire MVP is designed around one principle:

Everything must work perfectly on localhost before any production concerns are introduced.

No production infrastructure will be built.

No cloud architecture will be considered.

No ERP integrations will be developed.

Instead,

the Finance Simulation Environment will act as the entire business.

Why This Approach?

Because AI systems fail for reasons that are unrelated to deployment.

Examples:

choosing incorrect tools
misunderstanding user intent
forgetting conversation history
hallucinating finance data
extracting incorrect parameters
poor reasoning

These problems must be solved before worrying about scalability.

Development Philosophy

Every engineering decision should answer one question:

Does this improve the quality of the AI Finance Assistant?

If the answer is "No,"

it does not belong in the MVP.

Chapter 3 — Engineering Principles
Purpose

This chapter defines the engineering rules that govern the entire project.

These principles are non-negotiable.

Every new feature, every pull request, every architectural decision should be evaluated against them.

If a proposed implementation violates one of these principles, it should be redesigned before it is merged.

Principle 1 — AI is the Decision Maker, Not the Database

The LLM should never directly access PostgreSQL.

The LLM should never generate SQL queries.

The LLM should never know table names.

The LLM should never know relationships between database tables.

Instead, the LLM should think in terms of business concepts.

Example:

Instead of thinking:

SELECT * FROM invoices
WHERE status='unpaid'

The assistant should think:

"I need unpaid invoices."

which becomes

get_unpaid_invoices()

The tool executes the database query.

The AI only reasons over the returned information.

Principle 2 — Every Business Operation is a Tool

Every business capability should exist as a Python function.

Examples:

get_unpaid_invoices()

get_customer()

find_duplicate_invoice()

get_vendor_balance()

match_invoice_to_purchase_order()

send_payment_reminder()

generate_aging_report()

The assistant should never invent new operations.

If a capability does not exist as a tool,

it does not exist.

Principle 3 — Natural Language First

Users should never have to learn commands.

The assistant must understand normal English.

Good:

Show unpaid invoices.

Good:

Which customers still owe us money?

Good:

I'm looking for invoices that haven't been paid yet.

Bad:

/find_invoice unpaid

Bad:

status: unpaid

Bad:

invoice overdue

No keyword matching should exist.

Principle 4 — ChatGPT-Level Conversation

The assistant should behave like ChatGPT.

Meaning:

It should

understand incomplete sentences
infer user intent
ask clarification questions when needed
maintain conversation context
understand references

Example:

User:

Show overdue invoices.

↓

Assistant shows 30 invoices.

↓

User:

Only those above $5,000.

The assistant must understand what "those" refers to.

Principle 5 — Reason Before Acting

The assistant should never perform actions blindly.

Every action follows this sequence:

Understand

↓

Reason

↓

Choose Tool

↓

Execute

↓

Verify

↓

Respond

No shortcuts.

Principle 6 — The LLM Never Contains Business Logic

This is one of the most important rules.

Business rules belong in Python.

Not inside prompts.

Bad example:

Prompt:

Never approve invoices above $10,000.

Good:

Python:

if invoice.amount > 10000:
    raise ApprovalRequired()

The LLM should not enforce business policy.

It should explain business policy.

Principle 7 — Finance Simulator is the Source of Truth

During MVP development,

the Finance Simulation Environment is considered the ERP.

Everything must work against it.

If it doesn't work with the simulator,

it doesn't work.

Principle 8 — Every Feature Must Be Testable

Every new capability requires automated tests.

For example,

Suppose we build:

find_duplicate_invoice()

We should immediately create evaluation scenarios.

User:

Find duplicate invoices.

Expected tool:

find_duplicate_invoice()

Expected parameters:

Correct.

Expected response:

Correct.

If these tests don't exist,

the feature is incomplete.

Principle 9 — AI Responses Must Be Explainable

The assistant should never return mysterious answers.

Instead,

it should explain its reasoning.

Example:

User:

Why did you recommend paying Vendor A first?

Good answer:

Vendor A's invoice is 75 days overdue and carries a late payment penalty beginning next week. Vendor B's invoice is not due for another 20 days, so paying Vendor A first reduces immediate financial risk.

Not:

Because I think it's better.

Principle 10 — Hallucinations Are Treated as Bugs

If the simulator does not contain information,

the assistant should never invent it.

Correct:

I couldn't find any invoice matching INV-4502.

Incorrect:

Invoice INV-4502 was paid yesterday.

Every hallucination is considered a software defect.

Principle 11 — The AI Never Guesses Missing Parameters

If required information is missing,

the assistant should ask.

Example:

User:

Show invoices.

Assistant:

Would you like all invoices, unpaid invoices, or overdue invoices?

Never assume.

Principle 12 — Separation of Responsibilities

Every component has one responsibility.

Frontend

Responsible for:

chat interface
displaying responses
displaying tables
user interaction

Nothing else.

FastAPI

Responsible for:

orchestration
API endpoints
conversation management
tool execution
routing
LLM

Responsible for:

understanding language
reasoning
choosing tools
explaining results
Finance Tools

Responsible for:

retrieving data
updating data
deterministic business operations
Finance Simulator

Responsible for:

acting as the ERP
storing finance information
providing realistic business data
Principle 13 — Modular Architecture

Every module should be replaceable.

Example:

Today

Finance Simulator

Later

ERPNext

Later

SAP

The AI should never notice the difference.

Only the adapter changes.

Principle 14 — Localhost First Development

Every feature must work completely on localhost before considering production.

No feature should depend on cloud infrastructure.

No feature should require enterprise integrations.

No feature should require customer data.

Local development is the primary development environment.

Principle 15 — Evaluation-Driven Development

Traditional software uses Test-Driven Development (TDD).

For AI systems, we will use Evaluation-Driven Development (EDD).

The workflow is:

Define the capability.
Write evaluation cases.
Build the tool.
Integrate the tool.
Measure accuracy.
Improve prompts or tools until the evaluation passes.

Example:

Capability:

Find overdue invoices.

Evaluation Set:

100 different user phrasings.
Expected tool selection.
Expected parameters.
Expected final response.

A capability is only considered complete when it consistently passes its evaluation suite.

Principle 16 — Build for Future Integration Without Depending on It

Although this MVP uses the Finance Simulation Environment, every interface should be designed as if it will later connect to a real ERP.

That means tools should expose business operations like:

get_unpaid_invoices()
create_payment_reminder()
match_invoice_to_purchase_order()

rather than simulator-specific functions.

The simulator is an implementation detail, not part of the public interface.

Engineering Principles Summary

Every engineer working on this project should remember these core rules:

The AI reasons; tools execute.
The AI never accesses the database directly.
Natural language is the only user interface.
Business logic belongs in code, not prompts.
The Finance Simulator is the development ERP.
Every feature must have automated evaluations.
Hallucinations are bugs.
The architecture must remain modular.
Localhost is the primary target environment.
Build confidence through evaluation before adding new capabilities.

Chapter 3 — Engineering Principles
Purpose

This chapter defines the engineering rules that govern the entire project.

These principles are non-negotiable.

Every new feature, every pull request, every architectural decision should be evaluated against them.

If a proposed implementation violates one of these principles, it should be redesigned before it is merged.

Principle 1 — AI is the Decision Maker, Not the Database

The LLM should never directly access PostgreSQL.

The LLM should never generate SQL queries.

The LLM should never know table names.

The LLM should never know relationships between database tables.

Instead, the LLM should think in terms of business concepts.

Example:

Instead of thinking:

SELECT * FROM invoices
WHERE status='unpaid'

The assistant should think:

"I need unpaid invoices."

which becomes

get_unpaid_invoices()

The tool executes the database query.

The AI only reasons over the returned information.

Principle 2 — Every Business Operation is a Tool

Every business capability should exist as a Python function.

Examples:

get_unpaid_invoices()

get_customer()

find_duplicate_invoice()

get_vendor_balance()

match_invoice_to_purchase_order()

send_payment_reminder()

generate_aging_report()

The assistant should never invent new operations.

If a capability does not exist as a tool,

it does not exist.

Principle 3 — Natural Language First

Users should never have to learn commands.

The assistant must understand normal English.

Good:

Show unpaid invoices.

Good:

Which customers still owe us money?

Good:

I'm looking for invoices that haven't been paid yet.

Bad:

/find_invoice unpaid

Bad:

status: unpaid

Bad:

invoice overdue

No keyword matching should exist.

Principle 4 — ChatGPT-Level Conversation

The assistant should behave like ChatGPT.

Meaning:

It should

understand incomplete sentences
infer user intent
ask clarification questions when needed
maintain conversation context
understand references

Example:

User:

Show overdue invoices.

↓

Assistant shows 30 invoices.

↓

User:

Only those above $5,000.

The assistant must understand what "those" refers to.

Principle 5 — Reason Before Acting

The assistant should never perform actions blindly.

Every action follows this sequence:

Understand

↓

Reason

↓

Choose Tool

↓

Execute

↓

Verify

↓

Respond

No shortcuts.

Principle 6 — The LLM Never Contains Business Logic

This is one of the most important rules.

Business rules belong in Python.

Not inside prompts.

Bad example:

Prompt:

Never approve invoices above $10,000.

Good:

Python:

if invoice.amount > 10000:
    raise ApprovalRequired()

The LLM should not enforce business policy.

It should explain business policy.

Principle 7 — Finance Simulator is the Source of Truth

During MVP development,

the Finance Simulation Environment is considered the ERP.

Everything must work against it.

If it doesn't work with the simulator,

it doesn't work.

Principle 8 — Every Feature Must Be Testable

Every new capability requires automated tests.

For example,

Suppose we build:

find_duplicate_invoice()

We should immediately create evaluation scenarios.

User:

Find duplicate invoices.

Expected tool:

find_duplicate_invoice()

Expected parameters:

Correct.

Expected response:

Correct.

If these tests don't exist,

the feature is incomplete.

Principle 9 — AI Responses Must Be Explainable

The assistant should never return mysterious answers.

Instead,

it should explain its reasoning.

Example:

User:

Why did you recommend paying Vendor A first?

Good answer:

Vendor A's invoice is 75 days overdue and carries a late payment penalty beginning next week. Vendor B's invoice is not due for another 20 days, so paying Vendor A first reduces immediate financial risk.

Not:

Because I think it's better.

Principle 10 — Hallucinations Are Treated as Bugs

If the simulator does not contain information,

the assistant should never invent it.

Correct:

I couldn't find any invoice matching INV-4502.

Incorrect:

Invoice INV-4502 was paid yesterday.

Every hallucination is considered a software defect.

Principle 11 — The AI Never Guesses Missing Parameters

If required information is missing,

the assistant should ask.

Example:

User:

Show invoices.

Assistant:

Would you like all invoices, unpaid invoices, or overdue invoices?

Never assume.

Principle 12 — Separation of Responsibilities

Every component has one responsibility.

Frontend

Responsible for:

chat interface
displaying responses
displaying tables
user interaction

Nothing else.

FastAPI

Responsible for:

orchestration
API endpoints
conversation management
tool execution
routing
LLM

Responsible for:

understanding language
reasoning
choosing tools
explaining results
Finance Tools

Responsible for:

retrieving data
updating data
deterministic business operations
Finance Simulator

Responsible for:

acting as the ERP
storing finance information
providing realistic business data
Principle 13 — Modular Architecture

Every module should be replaceable.

Example:

Today

Finance Simulator

Later

ERPNext

Later

SAP

The AI should never notice the difference.

Only the adapter changes.

Principle 14 — Localhost First Development

Every feature must work completely on localhost before considering production.

No feature should depend on cloud infrastructure.

No feature should require enterprise integrations.

No feature should require customer data.

Local development is the primary development environment.

Principle 15 — Evaluation-Driven Development

Traditional software uses Test-Driven Development (TDD).

For AI systems, we will use Evaluation-Driven Development (EDD).

The workflow is:

Define the capability.
Write evaluation cases.
Build the tool.
Integrate the tool.
Measure accuracy.
Improve prompts or tools until the evaluation passes.

Example:

Capability:

Find overdue invoices.

Evaluation Set:

100 different user phrasings.
Expected tool selection.
Expected parameters.
Expected final response.

A capability is only considered complete when it consistently passes its evaluation suite.

Principle 16 — Build for Future Integration Without Depending on It

Although this MVP uses the Finance Simulation Environment, every interface should be designed as if it will later connect to a real ERP.

That means tools should expose business operations like:

get_unpaid_invoices()
create_payment_reminder()
match_invoice_to_purchase_order()

rather than simulator-specific functions.

The simulator is an implementation detail, not part of the public interface.

Engineering Principles Summary

Every engineer working on this project should remember these core rules:

The AI reasons; tools execute.
The AI never accesses the database directly.
Natural language is the only user interface.
Business logic belongs in code, not prompts.
The Finance Simulator is the development ERP.
Every feature must have automated evaluations.
Hallucinations are bugs.
The architecture must remain modular.
Localhost is the primary target environment.
Build confidence through evaluation before adding new capabilities.
End of Chapter 3

The next chapter will be Functional Requirements, where we will define every capability the MVP must provide, broken down into detailed user stories, expected behaviors, acceptance criteria, and implementation requirements. This will serve as the contract for what the MVP must do before we consider it feature-complete.

continue

Great. Now we move from philosophy to concrete product requirements.

This chapter defines exactly what the AI Finance Assistant must be able to do in the MVP.

Chapter 4 — Functional Requirements
Purpose

The goal of this chapter is to define the minimum set of capabilities required for a successful localhost MVP.

Each requirement includes:

Feature description

User story

Expected behavior

Acceptance criteria

FR-1 — Conversational Chat Interface
Description

Users must interact with the assistant through a chat interface similar to ChatGPT.

User Stories

As a finance employee,

I want to ask questions in plain English,

so that I don't need to learn any commands or filters.

Expected Behavior

Accept free-form text.

Support multi-turn conversations.

Display assistant responses in chat format.

Preserve conversation history during the session.

Acceptance Criteria

User can send a message.

Assistant responds within a few seconds.

Previous messages remain visible.

Conversation context is preserved.

FR-2 — Natural Language Understanding
Description

The assistant must understand finance questions expressed in different ways.

Examples
Equivalent Queries

All should trigger the same tool

"Show unpaid invoices."

"Which invoices haven't been paid?"

"Who still owes us money?"

"Outstanding invoices?"

"Customers with overdue invoices."

Acceptance Criteria

Different phrasings map to the same tool.

No keyword matching is used.

The assistant can infer intent from natural English.

FR-3 — Multi-Turn Conversation Memory
Description

The assistant must understand follow-up questions.

Example

User

Show overdue invoices.

Assistant

Displays 30 invoices.

User

Only those above $5,000.

Acceptance Criteria

Assistant understands what "those" refers to.

Context survives across multiple messages.

Follow-up filtering works correctly.

FR-4 — Finance Tool Calling
Description

The assistant must use structured tools rather than generating SQL.

Required Tool Categories

Category

	

Examples




Invoices

	

Get unpaid invoices, search invoices




Customers

	

Get customer balance, list overdue customers




Vendors

	

Get vendor information




Purchase Orders

	

Match invoice to PO




Reports

	

Generate aging report

Acceptance Criteria

LLM selects the correct tool.

Tool parameters are extracted correctly.

Tool execution succeeds.

Results are returned as structured JSON.

FR-5 — Unpaid Invoice Search
Description

Users can find unpaid invoices.

Example Queries

"Show unpaid invoices."

"What invoices are still outstanding?"

"Which customers haven't paid?"

Expected Response

Assistant returns a summarized list including:

Customer name

Invoice number

Amount

Due date

Days overdue

FR-6 — Overdue Invoice Filtering
Description

Users can filter invoices by overdue period.

Example Queries

"Show invoices overdue by more than 30 days."

"Which invoices are 60+ days late?"

"Customers overdue for at least 90 days."

Acceptance Criteria

Correct days value extracted.

Correct invoices returned.

Natural-language summary generated.

FR-7 — Customer Balance Lookup
Description

Users can ask about a specific customer.

Example

User

What is ABC Industries' outstanding balance?

Expected Response

ABC Industries has an outstanding balance of $14,500 across 3 unpaid invoices.

FR-8 — Duplicate Invoice Detection
Description

The assistant can identify potential duplicate invoices.

Example Queries

"Find duplicate invoices."

"Check whether invoice INV-2201 already exists."

Acceptance Criteria

Duplicates are detected correctly.

Matching invoices are shown.

False positives are minimized.

FR-9 — Invoice to Purchase Order Matching
Description

The assistant can compare invoices against purchase orders.

Example

User

Check whether invoice INV-4501 matches its purchase order.

Expected Response

The invoice matches PO-445. Vendor, amount, and line items are consistent.

FR-10 — Aging Report Generation
Description

The assistant can summarize receivables by aging bucket.

Expected Buckets

Bucket

	

Example




0–30 days

	

$120,000




31–60 days

	

$45,000




61–90 days

	

$18,000




90+ days

	

$9,000

FR-11 — Clarification Questions
Description

When a request is ambiguous, the assistant must ask for clarification.

Example

User

Show invoices.

Expected Response

Would you like all invoices, unpaid invoices, or overdue invoices?

FR-12 — Hallucination Prevention
Description

If data does not exist, the assistant must say so.

Correct

I couldn't find invoice INV-9999.

Incorrect

Invoice INV-9999 was paid yesterday.

FR-13 — Finance Simulation Environment
Description

The MVP must include a realistic fictional company.

Minimum Dataset

Entity

	

Minimum Count




Customers

	

500




Vendors

	

150




Invoices

	

10,000




Purchase Orders

	

3,000




Payments

	

2,500




Expense Claims

	

500

FR-14 — Automated Evaluation Suite
Description

The project must include automated AI evaluations.

Evaluation Categories

Intent recognition

Tool selection

Parameter extraction

Response correctness

Conversation memory

Hallucination resistance

FR-15 — Local CI Pipeline
Description

Every commit should automatically run validation checks.

Required CI Checks

Unit tests

Tool tests

Finance simulator tests

AI evaluation suite

Linting

Type checking




Chapter 5 — Non-Functional Requirements (NFR)
Purpose

The Functional Requirements define what the assistant can do.

The Non-Functional Requirements define how well it must do those things.

Unlike traditional applications, an AI assistant cannot simply "work."

It must also be:

accurate
reliable
explainable
predictable
easy to evaluate

These requirements define the quality bar for the MVP.

NFR-1 — Natural Conversation
Objective

The assistant should feel like talking to ChatGPT.

The user should never feel like they are interacting with a search engine or a rule-based chatbot.

Requirements

The assistant must:

understand conversational English
understand incomplete sentences
understand follow-up questions
ask clarifying questions when necessary
avoid robotic responses
avoid exposing implementation details
Good Example

User:

Who hasn't paid us?

Assistant:

I found 18 customers with overdue invoices. The three largest outstanding balances are ABC Industries ($18,200), Future Corp ($15,600), and Northwind Traders ($11,900). Would you like the full list or only invoices older than 60 days?

Poor Example
Command recognized.

Executing get_unpaid_invoices().

Users should never see internal operations.

NFR-2 — No Keyword Dependency

This is one of the most important requirements.

The assistant must never rely on keyword matching.

Instead,

it must understand user intent.

Example

All of these should produce identical behavior.

Outstanding invoices

Show unpaid invoices

Which invoices are still unpaid?

Who owes us money?

Customers with unpaid balances

If one succeeds while another fails,

that is considered a defect.

NFR-3 — Context Retention

The assistant must remember previous messages within the active conversation.

Example

User:

Show invoices overdue by more than 60 days.

Assistant displays results.

User:

Only show invoices above $10,000.

The assistant must understand that the second request refers to the previous result.

Acceptance Goal

Conversation context should remain accurate throughout a normal working session.

NFR-4 — Response Accuracy

The assistant should provide factually correct answers based only on simulator data.

It must never invent:

invoices
customers
vendors
balances
payment dates

If information cannot be found,

the assistant should clearly state that.

NFR-5 — Tool Selection Accuracy

One of the most important metrics.

For every evaluation prompt,

the assistant should choose the correct tool.

Example

User:

Find duplicate invoices.

Correct:

find_duplicate_invoice()

Incorrect:

get_unpaid_invoices()
MVP Target

Tool selection accuracy should consistently exceed 95% on the evaluation dataset.

NFR-6 — Parameter Extraction Accuracy

Selecting the correct tool is only half the problem.

The assistant must also extract the correct parameters.

Example

User

Show invoices over $15,000 that are overdue by more than 90 days.

Correct extraction:

Minimum Amount: 15000

Minimum Days Overdue: 90

Incorrect extraction:

Amount: 1500

Days: 9
MVP Target

Parameter extraction accuracy should consistently exceed 95% on the evaluation dataset.

NFR-7 — Hallucination Rate

Hallucinations are considered software defects.

The assistant must never fabricate:

invoices
balances
customers
payment history
purchase orders

If information does not exist,

the assistant should respond honestly.

MVP Goal

Hallucination rate should be effectively zero within the Finance Simulation Environment.

NFR-8 — Explainability

The assistant should explain why it produced a recommendation.

Example

User

Why should we pay Vendor A first?

Good answer

Vendor A's invoice is 75 days overdue and begins accruing late fees next week. Vendor B's invoice is due in 18 days, so prioritizing Vendor A reduces immediate financial risk.

The explanation should be grounded in retrieved data.

NFR-9 — Predictability

The same question should produce consistent tool selection and similar answers.

Small wording differences should not drastically change behavior.

This is especially important for building user trust.

NFR-10 — Local Performance

Because the MVP runs entirely on localhost, we should establish practical performance goals rather than production-scale targets.

Initial Targets
Chat response should begin within approximately 3 seconds for typical queries.
Simple tool calls should complete within 1 second under normal conditions.
Complex queries involving multiple tool calls should remain responsive and provide progress feedback if needed.

These are goals to guide optimization, not strict production SLAs.

NFR-11 — Error Handling

The assistant should fail gracefully.

Examples:

Instead of:

Internal server error

The assistant should respond with something like:

I couldn't retrieve invoice information because the finance simulator is currently unavailable. Please try again after restarting the simulator.

The user should receive helpful information without exposing internal stack traces.

NFR-12 — Modularity

Every major component should be replaceable without affecting the others.

Example:

Today

Finance Simulator

Later

ERPNext

The AI should require minimal or no changes because it interacts through the tool layer.

NFR-13 — Maintainability

The codebase should follow clean architecture principles.

Business logic should never be mixed into:

prompts
frontend code
database queries

Each layer should have a clearly defined responsibility.

NFR-14 — Testability

Every feature introduced into the assistant must have corresponding automated tests.

For AI capabilities, this includes evaluation scenarios in addition to traditional unit tests.

A feature without tests is considered incomplete.

NFR-15 — Local-First Development

The application must be fully usable on a single development machine.

No cloud services should be required beyond access to an LLM provider (or a local model, if configured).

Developers should be able to clone the repository, generate the Finance Simulation Environment, and begin testing without requiring enterprise infrastructure.

NFR-16 — Observability (Development Focus)

Even though we're not building production monitoring, the MVP should capture enough information to debug the AI.

Every interaction should log:

User message
Conversation ID
Selected tool(s)
Tool parameters
Tool execution status
Tool results (where appropriate)
Final assistant response
Response time

These logs will be invaluable when investigating incorrect tool choices or reasoning errors.

Quality Targets Summary
Metric	MVP Target
Natural language understanding	Conversational, no keyword dependency
Tool selection accuracy	>95%
Parameter extraction accuracy	>95%
Hallucination rate	Effectively 0 within simulator
Context retention	Maintains conversation throughout a session
Response consistency	High
Automated evaluation coverage	Required for every capability
Local execution	Fully functional on localhost



Chapter 6 — MVP Scope
Purpose

This chapter defines the exact boundaries of the MVP.

Every feature in this chapter is included because it directly contributes to validating the core hypothesis:

Can an AI Finance Assistant understand natural language, reason over finance data, select the correct tools, and reliably assist finance employees on localhost?

Anything that does not contribute to answering that question is out of scope.

Core Product Goal

The MVP is not an ERP.

The MVP is not an automation platform.

The MVP is not a workflow builder.

The MVP is not a SaaS application.

The MVP is an AI Finance Copilot operating against a simulated finance environment.

What Success Looks Like

By the end of the MVP, a finance employee should be able to open the application and naturally ask questions like:

Which customers haven't paid us?

Show invoices overdue by more than 60 days.

Find duplicate invoices.

Match invoice INV-10024 to its purchase order.

Which vendors have the highest outstanding balances?

Generate an aging report.

The assistant should answer accurately, explain its reasoning where appropriate, and maintain context throughout the conversation.

Included Features
1. Conversational Chat Interface

The primary interface is a ChatGPT-style conversation.

Capabilities:

Natural language input
Markdown responses
Tables for structured data
Conversation history
Follow-up questions
Context retention

This is the only interface for the MVP.

We will not build dashboards full of filters and forms.

2. Finance Tool Library

The assistant's capabilities come from deterministic tools.

Invoice Tools
get_invoice()

search_invoices()

get_unpaid_invoices()

get_overdue_invoices()

find_duplicate_invoice()
Customer Tools
get_customer()

get_customer_balance()

list_overdue_customers()
Vendor Tools
get_vendor()

get_vendor_balance()
Purchase Order Tools
get_purchase_order()

match_invoice_to_purchase_order()
Reporting Tools
generate_aging_report()

get_cash_position()

Design Rule: Every tool should perform one clear business operation and return structured JSON. The LLM is responsible for interpreting that JSON and communicating the results.

3. Finance Simulation Environment

This is the heart of the MVP.

We are not connecting to a real ERP.

Instead, we'll create a realistic fictional company.

The simulated company includes:
Customers
Vendors
Invoices
Purchase Orders
Payments
Expense Claims
Employees
Company Policies

The data must be internally consistent.

Example:

Customer A owns Invoice #1001.
Invoice #1001 references Purchase Order #445.
Purchase Order #445 belongs to Vendor X.
Payments update outstanding balances correctly.

The simulator should behave like a real finance system from the AI's perspective.

4. Conversation Memory

The assistant must remember context during an active session.

Example:

User

Show overdue invoices.

↓

Assistant

Displays invoices.

↓

User

Which of those belong to ABC Industries?

↓

The assistant should understand that "those" refers to the invoices from the previous response.

5. Structured Tool Calling

Every business operation follows the same pipeline:

User
   │
   ▼
LLM understands intent
   │
   ▼
LLM selects tool(s)
   │
   ▼
FastAPI executes tool(s)
   │
   ▼
Finance Simulator returns JSON
   │
   ▼
LLM reasons over results
   │
   ▼
Natural-language response

This pipeline must be used consistently across all features.

6. AI Evaluation Framework

The MVP includes a first-class evaluation system.

Every capability must have automated evaluation scenarios.

For example:

Prompt

Who owes us more than $10,000?

Expected:

Correct tool
Correct parameters
Correct reasoning
Correct response

The evaluation suite should grow alongside the product.

7. Finance Data Generator

The simulator's data should not be handwritten.

Instead, we'll build a generator that creates realistic business data.

It should generate:
Customers
Vendors
Products or services
Invoices
Purchase Orders
Payments
Credit limits
Payment terms
Due dates
Late payments
Duplicate invoices (for testing)
Purchase order mismatches (for testing)

The generator should support different dataset sizes (e.g., "small", "medium", "large") so developers can quickly switch between fast local tests and larger evaluation runs.

8. Development Logging

The MVP should log every AI interaction.

Each interaction should include:

User prompt
Conversation ID
Selected tool(s)
Tool parameters
Tool execution time
Tool output (or a summarized form if large)
Final assistant response
Any errors encountered

These logs are essential for debugging and improving the assistant.

9. Local CI Pipeline

Every commit should automatically execute:

Unit tests
Tool tests
Finance simulator tests
AI evaluation suite
Linting
Type checking

The CI pipeline's purpose is to prevent regressions during development.

There is no deployment stage in the MVP.

Explicitly Out of Scope

The following features are intentionally excluded.

ERP Integrations

Not included:

SAP
Oracle
Microsoft Dynamics
NetSuite
ERPNext
Odoo

These will be addressed after the AI proves itself in the simulator.

Banking Integrations

Not included:

Bank APIs
Payment execution
Wire transfers
Open Banking integrations
Authentication

No login system.

No user accounts.

No permissions.

A single local developer instance is sufficient.

Multi-Tenancy

The MVP supports one simulated company.

Multiple organizations will be introduced only after the core assistant is validated.

Cloud Infrastructure

Not included:

AWS
Azure
Google Cloud
Kubernetes
Load balancers
Auto-scaling
Production databases
Production Monitoring

No production observability stack.

No uptime monitoring.

No alerting systems.

Development logging is sufficient for the MVP.

Billing & SaaS Features

Not included:

Subscriptions
Payment gateways
Licensing
Organization management
Workflow Automation

The assistant may recommend actions, but it should not autonomously execute business workflows in the MVP.

For example:

✅ "I found 18 overdue invoices and drafted reminder emails."

❌ Automatically sending those reminders without user confirmation.

The focus is on building trust before introducing automation.

MVP Deliverables

The MVP will be considered complete when the following are available:

A local Next.js application with a conversational interface.
A FastAPI backend orchestrating AI interactions.
A Finance Simulation Environment with realistic data.
A deterministic finance tool library.
An LLM capable of selecting and chaining tools.
Session-based conversation memory.
An automated AI evaluation framework.
A local CI pipeline.
Complete documentation for setup and development.
Definition of Done

The MVP is complete when a developer can:

Clone the repository.
Install dependencies.
Generate a finance simulation dataset.
Start the frontend and backend locally.
Ask natural-language finance questions.
Observe the assistant selecting the correct tools.
Verify responses through the evaluation framework.
Run the full test suite successfully.

If all of those steps work reliably, we have achieved the MVP's goal.


Chapter 7 — System Architecture
Purpose

This chapter defines the complete architecture of the AI Finance Assistant MVP.

The architecture is designed around one principle:

The LLM reasons. The application executes.

This separation ensures the system remains:

Modular
Testable
Explainable
Easy to debug
Easy to replace components
Ready for future ERP integrations
High-Level Architecture
                           USER
                             │
                             ▼
                   Next.js Chat Interface
                             │
                     HTTPS / REST API
                             │
                             ▼
                   FastAPI Orchestrator
                             │
     ┌───────────────┬───────────────┬────────────────┐
     │               │               │                │
     ▼               ▼               ▼                ▼
Conversation     LLM Service     Tool Engine    Evaluation Engine
Memory
     │                               │
     │                               ▼
     │                      Finance Tool Library
     │                               │
     │                               ▼
     │                    Finance Simulation Layer
     │                               │
     └───────────────────────────────▼
                          PostgreSQL Database

Notice something important.

The LLM never talks to PostgreSQL.

The LLM never executes SQL.

The LLM never modifies business data.

FastAPI controls everything.

Why FastAPI is the Orchestrator

Many AI applications allow the LLM to call tools directly.

We will not do that.

Instead:

User

↓

FastAPI

↓

LLM

↓

FastAPI validates tool call

↓

Tool executes

↓

FastAPI validates output

↓

LLM summarizes

↓

FastAPI returns response

FastAPI remains in control throughout the entire request lifecycle.

This makes the system easier to secure, debug, and extend.

Component Responsibilities

Every component has exactly one responsibility.

No exceptions.

1. Frontend (Next.js)
Responsibilities
Chat interface
Render markdown
Render tables
Display charts (future)
Display loading states
Display tool execution progress
Maintain local UI state

The frontend should never contain business logic.

It should never decide which tools to call.

It should never contain finance rules.

It is purely a presentation layer.

2. FastAPI (Application Brain)

FastAPI is not just an API server.

It is the application's orchestration layer.

Responsibilities:

Session management
Conversation management
Calling the LLM
Validating tool calls
Executing tools
Managing memory
Logging
Error handling
Returning responses

Think of FastAPI as the project manager.

Everything passes through it.

3. LLM Service

The LLM has only four responsibilities.

Responsibility 1

Understand user intent.

Example:

Show invoices older than 60 days.

↓

Intent:

Find overdue invoices
Responsibility 2

Choose the correct tool(s).

Example:

get_overdue_invoices(days=60)
Responsibility 3

Interpret tool outputs.

The LLM receives JSON.

Example

[
  {
    "customer":"ABC",
    "amount":12000
  }
]

It converts this into human-friendly language.

Responsibility 4

Generate responses.

The LLM communicates naturally.

It never performs business operations itself.

4. Conversation Memory

Conversation Memory is separate from the LLM.

Its responsibilities:

Store previous messages
Store previous tool calls
Store assistant responses
Retrieve relevant context

The LLM should receive only the relevant conversation history, not the entire database or every past message.

5. Tool Engine

The Tool Engine is a deterministic execution layer.

It exposes Python functions to the LLM through FastAPI.

Example:

get_unpaid_invoices()

Internally,

it may execute SQL,

but the LLM never sees that.

The Tool Engine is responsible for:

Validating parameters
Calling business services
Returning structured JSON
Handling execution errors
6. Finance Tool Library

This layer contains reusable business capabilities.

Example categories:

Invoices

Customers

Vendors

Purchase Orders

Reports

Each tool should perform exactly one business operation.

Example:

Good:

get_customer_balance()

Bad:

do_everything()

Tools should be:

small
deterministic
reusable
independently testable
7. Finance Simulation Layer

This replaces the ERP.

Responsibilities:

Simulate finance operations
Store business data
Return realistic responses
Behave like a real ERP

It should not know anything about AI.

It simply provides finance functionality.

8. PostgreSQL

The database stores:

Finance data:

customers
vendors
invoices
purchase orders
payments
expenses

Application data:

conversations
tool logs
evaluation logs

Notice something.

We intentionally keep AI data separate from finance data.

Request Lifecycle

Let's walk through a complete request.

Step 1

User asks:

Which customers haven't paid us in more than 60 days?

Step 2

Next.js sends request.

POST /chat
Step 3

FastAPI receives request.

FastAPI:

retrieves conversation
retrieves memory
prepares prompt
Step 4

LLM receives:

Conversation

+

Available tools

+

Tool descriptions

The LLM decides:

get_overdue_invoices(days=60)
Step 5

FastAPI validates.

Is tool valid?

Is parameter valid?

If yes,

execute.

Step 6

Tool executes.

Finance Simulator

↓

PostgreSQL

↓

JSON
Step 7

FastAPI sends JSON back to LLM.

Example

[
    {
        "customer":"ABC Industries",
        "amount":15400
    }
]
Step 8

LLM summarizes.

Example

I found 12 customers with invoices overdue by more than 60 days. ABC Industries has the largest outstanding balance at $15,400.

Step 9

FastAPI logs:

prompt
tool
parameters
response
execution time
Step 10

Frontend displays answer.

Done.

Component Dependency Rules

To keep the architecture clean, dependencies should flow in one direction only:

Frontend
    │
    ▼
FastAPI
    │
    ▼
LLM Service
    │
    ▼
Tool Engine
    │
    ▼
Finance Simulator
    │
    ▼
Database

Rules:

The frontend never talks directly to the database.
The LLM never talks directly to the database.
The Tool Engine never calls the frontend.
The Finance Simulator never calls the LLM.
The database never contains business logic.

This prevents circular dependencies and keeps each layer focused.

Proposed Backend Folder Structure
backend/
│
├── app/
│   ├── api/                 # FastAPI endpoints
│   ├── core/                # Configuration, settings, logging
│   ├── llm/                 # LLM client and prompt management
│   ├── orchestration/       # Chat orchestration and workflow control
│   ├── memory/              # Conversation memory management
│   ├── tools/               # Finance tool definitions
│   ├── services/            # Business services used by tools
│   ├── simulator/           # Finance simulator logic and data generator
│   ├── models/              # SQLAlchemy models
│   ├── repositories/        # Database access layer
│   ├── evaluations/         # AI evaluation framework
│   ├── tests/               # Unit and integration tests
│   └── main.py
│
├── scripts/
│   ├── seed_simulator.py
│   └── generate_test_data.py
│
├── pyproject.toml
└── README.md

Notice an important design choice:

There is no SQL inside the tools.

The tools call services, and the services use repositories.

That keeps the business logic reusable and testable.

Architectural Principles Reinforced

This architecture enforces every engineering principle we've defined:

FastAPI orchestrates the application.
The LLM reasons but never performs business operations.
Tools are deterministic and independently testable.
Business logic lives in services, not prompts.
The Finance Simulator behaves like a real ERP.
The database is hidden behind repositories.
Every layer has a single responsibility.


Chapter 8 — AI Architecture
Purpose

This chapter defines the cognitive architecture of the AI Finance Assistant.

Unlike traditional software, where intelligence is encoded directly into code, our system separates reasoning from execution.

The Large Language Model (LLM) is responsible for understanding language, planning, and reasoning.

The application is responsible for deterministic execution.

The guiding principle is:

The LLM decides what should happen. FastAPI decides how it happens.

AI Philosophy

The assistant should behave like a highly capable finance analyst.

It should not behave like:

a keyword search engine
a rule-based chatbot
a SQL generator
an ERP interface

Instead, it should demonstrate the following abilities:

Understand natural English.
Infer user intent.
Ask clarifying questions when necessary.
Select the appropriate finance tools.
Interpret structured finance data.
Explain results clearly.
Maintain conversational context.
Avoid making unsupported assumptions.
The AI Decision Loop

Every user request follows the same reasoning cycle.

                User Message
                      │
                      ▼
         Understand User Intent
                      │
                      ▼
      Retrieve Relevant Conversation Context
                      │
                      ▼
      Determine Whether Clarification Is Needed
                      │
              Yes ─────────► Ask Clarifying Question
                      │
                     No
                      ▼
          Select Required Tool(s)
                      │
                      ▼
        FastAPI Executes Tool(s)
                      │
                      ▼
          Receive Structured JSON
                      │
                      ▼
          Reason Over The Results
                      │
                      ▼
      Generate Natural Language Response
                      │
                      ▼
          Store Conversation Memory

Every request should follow this loop.

No shortcuts.

AI Responsibilities

The LLM has exactly six responsibilities.

Responsibility 1 — Understand Intent

The first job of the assistant is to understand what the user wants, not how they phrase it.

Example:

User:

Who still owes us money?

Intent:

Retrieve customers with unpaid invoices.

The wording is irrelevant.

Only the intent matters.

Responsibility 2 — Understand Context

Every message should be interpreted within the current conversation.

Example:

User:

Show overdue invoices.

Assistant returns results.

User:

Which ones are above $20,000?

The assistant should understand that "ones" refers to the invoices returned previously.

It should not ask the user to repeat themselves.

Responsibility 3 — Detect Ambiguity

If multiple interpretations are equally valid, the assistant should pause and ask.

Example:

User:

Show invoices.

Possible interpretations:

All invoices
Paid invoices
Unpaid invoices
Overdue invoices
Draft invoices

Instead of guessing:

The assistant asks:

Would you like all invoices, only unpaid invoices, or only overdue invoices?

Responsibility 4 — Select Tools

Once intent is understood,

the assistant determines which tools are required.

Some questions require one tool.

Others require several.

Example:

User:

Which vendors have the highest overdue balances?

Possible reasoning:

Need vendor balances.

Need overdue invoices.

Combine both.

Summarize.

The assistant plans before acting.

Responsibility 5 — Interpret Results

The assistant receives structured JSON.

Example:

[
    {
        "vendor":"ABC Supplies",
        "balance":14500
    }
]

The assistant transforms this into useful business language.

Example:

ABC Supplies currently has the highest overdue balance at $14,500.

The assistant should never expose raw JSON to users unless explicitly requested.

Responsibility 6 — Explain Results

The assistant should explain recommendations.

Example:

User:

Why did you recommend following up with ABC Industries?

Assistant:

ABC Industries has three unpaid invoices totaling $18,200. The oldest invoice is 82 days overdue, exceeding the company's standard payment terms.

Reasoning should always be grounded in retrieved facts.

System Prompt Philosophy

The system prompt should define behavior, not business logic.

Good prompt guidance:

You are an AI Finance Assistant.
Be concise.
Use available tools.
Ask for clarification when information is missing.
Never invent finance data.
Explain your reasoning clearly.

Bad prompt guidance:

Never approve invoices above $10,000.
Vendors over $20,000 require CFO approval.

Those are business rules.

They belong in code.

Tool Selection Strategy

The assistant should always choose the smallest set of tools needed to answer the question.

Example:

User:

Show unpaid invoices.

Correct:

get_unpaid_invoices()

Incorrect:

get_all_customers()

get_all_invoices()

get_vendor_list()

calculate_everything()

Efficient planning is part of intelligence.

Tool Chaining

Many requests require multiple tools.

Example:

User:

Which customers owe us the most money?

Possible execution plan:

Step 1

Retrieve unpaid invoices.

↓

Step 2

Group by customer.

↓

Step 3

Calculate totals.

↓

Step 4

Sort descending.

↓

Step 5

Summarize.

The assistant should be capable of planning multi-step reasoning.

Clarification Strategy

The assistant should ask clarification questions only when the missing information materially changes the answer.

Good clarification:

Which customer are you referring to?

Poor clarification:

Are you sure?

If a reasonable default exists, the assistant may use it but should clearly communicate the assumption.

Example:

I assumed you meant invoices overdue by more than 30 days. Let me know if you'd like a different threshold.

Hallucination Prevention

The assistant must never fabricate data.

When uncertain, it should:

Search using available tools.
If nothing is found, state that clearly.
Offer a helpful next step if appropriate.

Example:

I couldn't find an invoice with number INV-4502 in the Finance Simulation Environment. Could you verify the invoice number?

Honesty is always preferable to guessing.

Memory Strategy

Conversation memory should be retrieval-based, not "send everything."

Instead of passing the entire chat history to the LLM every time, FastAPI should retrieve only the relevant context.

For example:

Current question:

Which of those should we contact first?

Relevant context:

The previous assistant response listing overdue customers.
The user's earlier filter (e.g., "over 60 days").

Irrelevant context from much earlier in the conversation should not be included.

This keeps prompts smaller, cheaper, and more focused.

Response Style

The assistant should communicate like an experienced finance colleague.

Responses should be:

Professional
Clear
Direct
Concise by default
More detailed when requested

Avoid:

Technical jargon about the system.
References to tool names.
References to internal implementation.

The user should never see:

I called get_unpaid_invoices().

Instead, they should simply receive the answer.

Failure Handling

When something goes wrong, the assistant should distinguish between:

Missing Data

I couldn't find any overdue invoices matching those criteria.

Tool Failure

I couldn't retrieve invoice information because the finance service encountered an error. Please try again.

Ambiguous Request

Did you mean customer invoices or vendor invoices?

Different failures require different responses.

AI Evaluation Metrics

The AI should be evaluated on reasoning quality, not just correctness.

Key metrics include:

Metric	Description
Intent Recognition	Did the assistant understand what the user wanted?
Tool Selection	Did it choose the correct tool(s)?
Parameter Extraction	Were the correct arguments passed?
Tool Chaining	Were multiple tools orchestrated correctly?
Clarification Quality	Did it ask only when necessary?
Groundedness	Was the response supported by retrieved data?
Hallucination Rate	Did it invent any facts?
Conversation Memory	Did it correctly use prior context?
Explanation Quality	Were recommendations understandable and evidence-based?

These metrics will form the basis of the automated evaluation framework.

AI Architecture Principles

Every AI interaction should satisfy the following principles:

Understand intent before selecting tools.
Retrieve only the necessary conversation context.
Ask clarifying questions only when required.
Prefer deterministic tools over model knowledge.
Base every answer on retrieved data.
Explain recommendations using evidence.
Never fabricate information.
Keep responses conversational and professional.
Minimize the number of tool calls.
Learn nothing from production assumptions—the simulator is the current world.



Chapter 9 — Tool & Service Design Principles
Purpose

This chapter defines the engineering standards for designing tools and services within the AI Finance Assistant.

The goal is to ensure every tool is:

Predictable
Deterministic
Independently testable
Easy for the LLM to understand
Easy to replace
Easy to maintain

This chapter applies to every current and future domain supported by the platform.

Philosophy

The LLM should think in terms of business capabilities, not software implementation.

When a user asks:

Which customers haven't paid us?

The LLM should immediately recognize the business capability:

Retrieve unpaid invoices.

It should never think:

Which SQL query should I generate?
Which table contains invoices?
Which repository should I call?

Those implementation details belong to the application.

Tool Hierarchy

The application should be organized into distinct layers.

User
    │
    ▼
LLM
    │
    ▼
FastAPI Orchestrator
    │
    ▼
Tool Layer
    │
    ▼
Service Layer
    │
    ▼
Repository Layer
    │
    ▼
Database

Each layer has a single responsibility.

Layer Responsibilities
1. Tool Layer

Purpose:

Expose business capabilities to the AI.

Examples:

get_unpaid_invoices()

find_duplicate_invoice()

get_customer_balance()

generate_aging_report()

A tool should never know SQL.

A tool should never know table names.

A tool simply orchestrates business services.

2. Service Layer

Purpose:

Contain business logic.

Example:

InvoiceService

CustomerService

VendorService

ReportService

This layer answers questions like:

How is an aging report calculated?
How do we detect duplicate invoices?
What qualifies as overdue?

Business logic belongs here.

3. Repository Layer

Purpose:

Retrieve and persist data.

Repositories contain:

SQLAlchemy
PostgreSQL queries
CRUD operations

Nothing else.

Repositories should never contain business rules.

Tool Design Rules

Every tool should follow these rules.

Rule 1 — One Tool = One Business Capability

Good:

get_customer_balance()

Good:

find_duplicate_invoice()

Bad:

manage_finance()

Large "do everything" tools confuse the LLM.

Rule 2 — Tools Must Be Deterministic

Given identical inputs,

a tool should return identical outputs.

Example:

get_invoice(invoice_id=1001)

should always return the same invoice unless the underlying data changes.

The LLM should never wonder whether a tool behaves differently each time.

Rule 3 — Tools Must Be Independently Testable

Every tool should have:

Unit tests
Integration tests
AI evaluation scenarios

Example:

get_customer_balance("ABC")

can be tested without running the entire application.

Rule 4 — Tools Return Structured Data

Never return natural-language strings.

Incorrect:

return "Customer owes $12,000."

Correct:

{
    "customer":"ABC Industries",
    "balance":12000,
    "currency":"USD"
}

The LLM is responsible for transforming structured data into human-readable language.

Rule 5 — Keep Inputs Explicit

Avoid vague function signatures.

Bad:

search(data)

Good:

get_overdue_invoices(
    minimum_days=30,
    customer_id=None
)

Explicit inputs improve both readability and tool selection.

Rule 6 — Keep Outputs Predictable

Every execution path should return the same structure.

Example:

{
    "success": true,
    "data": [...],
    "errors": []
}

or

{
    "success": false,
    "data": [],
    "errors": [
        "Invoice not found."
    ]
}

Avoid changing response formats based on different conditions.

Rule 7 — Tools Should Not Call Other Tools

Tools should remain independent.

Instead of:

Tool A

↓

calls Tool B

↓

calls Tool C

the orchestration layer should coordinate multiple tool calls.

This makes execution easier to understand and evaluate.

Rule 8 — Services May Collaborate

Unlike tools,

services may collaborate.

Example:

ReportService

↓

InvoiceService

↓

CustomerService

This collaboration is hidden from the AI.

Rule 9 — The LLM Never Sees Internal Layers

The LLM knows only:

Tool names
Tool descriptions
Tool parameters

It should never know:

repositories
SQL
service classes
ORM models
database schemas

This abstraction keeps prompts stable even if the backend evolves.

Tool Naming Standard

Every tool should be named using clear business language.

Good examples:

get_invoice
search_invoices
get_customer_balance
find_duplicate_invoice
match_invoice_to_purchase_order
generate_aging_report

Avoid technical or ambiguous names such as:

execute_query
invoice_handler
finance_manager
process_request

A developer should understand a tool's purpose from its name alone.

Tool Metadata

Each tool should include metadata to help the LLM make good decisions.

For every tool, define:

Name
Description
Required parameters
Optional parameters
Return schema
Example usage
Common use cases
Error conditions

This metadata becomes part of the tool registration process.

Error Handling Standard

Every tool should distinguish between:

Validation Errors

Example:

Missing invoice number.

Business Errors

Example:

Invoice exists but has already been paid.

System Errors

Example:

Database unavailable.

These error types should be represented consistently so FastAPI and the LLM can respond appropriately.

Idempotency

Whenever possible, tools should be idempotent.

Calling:

get_invoice(1001)

ten times should have no side effects.

For future write operations (outside this MVP), actions like creating records or sending emails should use safeguards to avoid duplicate execution.

Versioning

Tool contracts should be treated as stable APIs.

If a breaking change is required:

Create a new version.
Deprecate the old version.
Update evaluations.
Update prompts.
Remove the old version only after all consumers migrate.

This discipline will become important as the platform grows.

Example End-to-End Flow
User
    │
    ▼
"Who owes us more than $10,000?"
    │
    ▼
LLM
    │
Select:
get_customer_balances(min_balance=10000)
    │
    ▼
FastAPI
    │
    ▼
Tool
    │
    ▼
CustomerService
    │
    ▼
CustomerRepository
    │
    ▼
PostgreSQL
    │
    ▼
Structured JSON
    │
    ▼
LLM summarizes results
    │
    ▼
User

Every request in the system should follow this pattern.

Tool Development Checklist

Before a new tool is merged into the project, it should satisfy the following checklist:

Performs exactly one business capability.
Has a clear business-oriented name.
Uses explicit input parameters.
Returns structured JSON.
Contains no SQL.
Contains no UI logic.
Contains no prompt logic.
Has unit tests.
Has integration tests.
Has AI evaluation scenarios.
Includes tool metadata.
Produces deterministic behavior.
Handles validation, business, and system errors consistently.

If any item is missing, the tool is not ready.

Architectural Outcome

By following these principles, the Finance Assistant gains several advantages:

The LLM remains focused on reasoning rather than implementation details.
Tools become reusable across multiple assistants and domains.
Business logic stays centralized in services.
The backend remains modular and testable.
Replacing the Finance Simulator with a real ERP later will primarily require changes in repositories and service adapters, not in the AI layer or prompts.


Chapter 10 — Finance Tool Architecture
Purpose

This chapter defines every business capability available to the AI Finance Assistant.

These tools form the assistant's "skills."

The LLM cannot perform any finance operation unless a corresponding tool exists.

Every tool represents a business capability that a finance employee performs in the real world.

Finance Capability Hierarchy

Instead of creating tools randomly, we'll organize them into business domains.

Finance
│
├── Accounts Receivable
│
├── Accounts Payable
│
├── Customers
│
├── Vendors
│
├── Purchase Orders
│
├── Payments
│
├── Reports
│
├── Cash Flow
│
└── Expense Management

This organization mirrors how real finance departments operate.

MVP Design Principle

One of the biggest mistakes AI startups make is exposing too many tools to the LLM.

A larger toolset does not automatically produce a smarter assistant.

Instead, it increases:

reasoning complexity
tool selection errors
latency
maintenance cost

Our goal is to expose only the highest-value capabilities.

I recommend limiting the initial MVP to around 20–30 carefully designed tools.

We can always expand later.

Domain 1 — Accounts Receivable (Highest Priority)

This is where most finance teams spend significant manual effort.

Capabilities
Retrieve unpaid invoices
get_unpaid_invoices()

Purpose:

Return all invoices that remain unpaid.

Retrieve overdue invoices
get_overdue_invoices(
    minimum_days=None,
    customer_id=None
)

Examples:

Show invoices overdue by 30 days.

Show ABC's overdue invoices.

Retrieve invoice details
get_invoice(
    invoice_number
)

Example:

Show invoice INV-1045.

Search invoices
search_invoices(
    filters
)

Examples:

amount
customer
status
due date
invoice number

This becomes the flexible search capability.

Retrieve customer balance
get_customer_balance(
    customer_name
)

Example:

How much does ABC Industries owe us?

List overdue customers
list_overdue_customers()

Returns

customer
total overdue amount
oldest invoice
Domain 2 — Accounts Payable
Retrieve vendor balance
get_vendor_balance(
    vendor
)
List unpaid vendor invoices
get_vendor_invoices()
Recommend payment priorities
recommend_invoice_payments()

Notice something.

This tool does not actually pay invoices.

It recommends payment order.

The reasoning happens inside the service layer using configurable business policies.

Domain 3 — Purchase Orders
Retrieve purchase order
get_purchase_order()
Match invoice to purchase order
match_invoice_to_purchase_order()

Returns

Matched

Amount mismatch

Vendor mismatch

Missing PO

Line item mismatch

This tool alone can save finance teams significant manual effort.

Domain 4 — Duplicate Detection

One of the most requested finance features.

find_duplicate_invoice()

Checks:

invoice number
vendor
amount
invoice date

Returns a confidence score and the matching records to aid human review.

Domain 5 — Reporting
Aging report
generate_aging_report()
Outstanding receivables
get_accounts_receivable_summary()
Outstanding payables
get_accounts_payable_summary()
Cash position
get_cash_position()
Domain 6 — Customer Intelligence

These are reasoning-focused capabilities.

Example:

identify_high_risk_customers()

Possible criteria:

chronic late payments
multiple overdue invoices
large outstanding balance
frequent payment disputes (future)

The exact scoring logic belongs in the service layer.

Domain 7 — Finance Analytics

These are higher-level business insights.

Examples:

identify_top_customers()

identify_top_vendors()

monthly_collection_summary()

largest_overdue_balances()

These tools summarize data rather than simply retrieving records.

Domain 8 — Expense Management (Future MVP Extension)

Not part of the initial build, but we should reserve the architecture.

Examples:

get_expense_claim()

approve_expense()

list_pending_expenses()
Tool Registry

Rather than exposing every Python function automatically, FastAPI should maintain a Tool Registry.

Example concept:

Tool Name: get_unpaid_invoices

Description:
Returns unpaid customer invoices.

Parameters:
customer_id (optional)
minimum_amount (optional)

Returns:
Invoice List

The LLM only sees this registry.

It never scans the codebase.

This makes tool discovery controlled and consistent.

Tool Composition

Many user requests require more than one tool.

Example:

User:

Which customers owe us the most money and have invoices overdue by more than 60 days?

Execution plan:

get_overdue_invoices(60)

↓

group by customer

↓

calculate totals

↓

sort descending

↓

LLM summarizes

Notice that we don't create a separate tool called:

get_customers_with_large_overdue_balances()

Instead, we compose simpler capabilities.

This keeps the tool library small and reusable.

Read vs. Write Operations

For the MVP, we should strongly prefer read-only tools.

Read Operations
Get invoice
Search invoices
Customer balance
Aging report
Duplicate detection
Cash position

These are safe and deterministic.

Write Operations (Deferred)

Examples:

send_payment_reminder()

approve_invoice()

create_payment()

modify_invoice()

These will be introduced later, once we have robust confirmation flows, audit logging, and permission models.

Service Mapping

Every tool should map to one or more services.

For example:

Tool	Service
get_unpaid_invoices()	InvoiceService
find_duplicate_invoice()	InvoiceService
match_invoice_to_purchase_order()	PurchaseOrderService
generate_aging_report()	ReportService
recommend_invoice_payments()	CashManagementService

This keeps the tool layer thin and the business logic centralized.

Finance Tool Roadmap

To avoid overwhelming development, we'll implement tools in phases.

Phase 1 (Core Retrieval)
Get invoice
Get unpaid invoices
Get overdue invoices
Search invoices
Get customer balance

This establishes the end-to-end pipeline.

Phase 2 (Analysis)
Aging report
Duplicate invoice detection
Vendor balance
Purchase order matching

This introduces more complex reasoning.

Phase 3 (Recommendations)
Payment prioritization
High-risk customer identification
Cash position
Receivable summaries

This moves from retrieval to decision support.

Only after these phases are stable should we consider write operations.

A Design Improvement: Domain Adapters

I'd like to introduce one additional architectural concept that will make future ERP integration much cleaner.

Instead of having services query repositories directly, we introduce Domain Adapters.

For example:

InvoiceService
       │
       ▼
InvoiceAdapter
       │
       ├── Finance Simulator Adapter
       ├── ERPNext Adapter
       ├── SAP Adapter
       └── Oracle Adapter

The InvoiceService always calls the InvoiceAdapter interface.

Today, the adapter implementation points to the Finance Simulator.

Tomorrow, you can swap in an ERPNext or SAP implementation without changing the service layer or the AI.

This is a classic dependency inversion pattern and fits perfectly with our long-term goal of supporting multiple ERP systems while keeping the AI and business logic unchanged.


Chapter 11 — Finance Simulation Environment
Purpose

The Finance Simulation Environment is the development ERP for the AI Finance Assistant.

It replaces:

SAP
Oracle
ERPNext
Microsoft Dynamics
NetSuite

during MVP development.

The assistant should never know it is talking to a simulator.

From the AI's perspective,

this is a real company.

Why Build a Simulator?

Without a simulator,

development becomes impossible.

Questions like:

Which invoices are overdue?

Who hasn't paid?

Show duplicate invoices.

require realistic business data.

Waiting for access to a real company's ERP introduces major obstacles:

Security concerns
Legal agreements
Data privacy
Lack of repeatability
Inconsistent datasets

A simulator solves all of these problems.

Design Philosophy

The simulator should model an entire company,

not just a collection of random tables.

Every record should belong to a believable business story.

Example:

ABC Industries

↓

Purchase Order #PO-1032

↓

Invoice #INV-7841

↓

Payment due in 30 days

↓

Payment received after 67 days

↓

Outstanding balance updated

Every entity should connect naturally to the next.

The Fictional Company

We'll create a single fictional organization.

Example:

Company Name

Northwind Manufacturing Ltd.

(The name is arbitrary—we can choose another later.)

The company should have:

Employees
Customers
Vendors
Products
Purchase Orders
Invoices
Payments
Expense Claims

The AI should feel like it works inside this company.

Business Domains

The simulator should model the following domains.

Customers

Vendors

Invoices

Payments

Purchase Orders

Products

Employees

Departments

Expense Claims

General Ledger (future)

Bank Accounts (future)

We don't need every ERP feature, only those required for the MVP.

Core Database Entities
Customers

Each customer should include:

Customer ID
Company Name
Industry
Contact Person
Email
Credit Limit
Payment Terms
Current Balance
Status (Active / Inactive)

Example:

ABC Industries

Credit Limit

$250,000

Payment Terms

Net 30
Vendors

Each vendor includes:

Vendor ID
Company Name
Category
Payment Terms
Outstanding Balance
Preferred Vendor flag
Products / Services

Although our assistant is finance-focused, invoices should reference actual products or services.

Example:

Industrial Pumps

Maintenance Service

Steel Components

Software License

This enables realistic purchase orders and invoices.

Purchase Orders

Every purchase order should include:

PO Number
Vendor
Date
Items
Quantities
Prices
Approval Status

Invoices can then reference these purchase orders.

Invoices

This becomes the largest dataset.

Each invoice should contain:

Invoice Number
Customer
Date
Due Date
Amount
Currency
Status
Linked Purchase Order (where applicable)
Payment Status

Some invoices should intentionally include inconsistencies for testing.

Payments

Payments should reference invoices.

Example:

Invoice

↓

Payment

↓

Remaining Balance

The simulator should support:

Full payments
Partial payments
Late payments
Early payments
Missing payments
Business Relationships

Nothing should exist in isolation.

Customer

↓

Invoices

↓

Payments

↓

Outstanding Balance

Likewise:

Vendor

↓

Purchase Order

↓

Invoice

↓

Payment

These relationships allow the AI to answer complex questions.

Data Generation Philosophy

One of the biggest mistakes in simulated datasets is producing random values.

Random data produces unrealistic business behavior.

Instead,

our generator should follow business rules.

Example:

If:

Customer has:

Net 30

then:

Most payments should arrive between:

25–45 days

Some customers should consistently pay late.

Some should always pay early.

Some should occasionally miss payments entirely.

This creates meaningful patterns for the AI to reason about.

Customer Personas

Instead of random customers,

create behavioral profiles.

Example:

Reliable Customer

Always pays within payment terms.

Slow Payer

Usually pays 30–60 days late.

High-Value Customer

Large invoices

Large credit limit

Usually pays on time.

Risky Customer

Multiple overdue invoices

Frequent late payments

Near credit limit.

Now the assistant can answer questions like:

Which customers are becoming payment risks?

without artificial logic.

Vendor Personas

Similarly:

Reliable Vendor

Premium Vendor

International Vendor

Occasionally Delayed Vendor

Preferred Vendor

Each profile influences payment recommendations and reporting.

Intentional Test Scenarios

This is one of the most important design decisions.

The simulator should intentionally create "messy" data.

Real companies are messy.

Examples:

Duplicate invoices

Two invoices with nearly identical numbers.

Incorrect purchase order amount

Invoice:

$12,500

Purchase Order:

$12,450

Missing purchase order

Invoice exists

No PO exists.

Partial payment

Invoice:

$8,000

Payment:

$5,000

Remaining:

$3,000

Credit limit exceeded

Customer:

Credit Limit:

$50,000

Outstanding Balance:

$63,000

Extremely overdue invoices

Some invoices:

120+

180+

365+

days overdue.

These scenarios are invaluable for testing the assistant's reasoning.

Scenario Packs

Rather than generating one fixed dataset, we'll support multiple predefined scenarios.

Examples:

Healthy Company

Most customers pay on time.

Very few overdue invoices.

Strong cash flow.

Cash Flow Crisis

Many overdue invoices.

Large outstanding receivables.

Late vendor payments.

Rapid Growth

Many new customers.

High invoice volume.

Large outstanding balances.

Fraud Detection

Many duplicate invoices.

Suspicious payment behavior.

These scenario packs allow us to test how the assistant behaves under different business conditions.

Data Scale

The simulator should support configurable sizes.

Profile	Customers	Invoices
Small	50	1,000
Medium	500	10,000
Large	5,000	100,000

This lets us balance development speed with realistic testing.

Reproducibility

One feature I'd strongly recommend is seeded data generation.

For example:

seed = 42

Running the generator with the same seed should always produce the same company.

Benefits:

Reproducible bugs
Stable evaluation results
Easier collaboration
Consistent CI tests

This is essential for debugging AI behavior.

Simulator API

The simulator should never expose SQL directly.

Instead, it exposes the same business interfaces that a future ERP adapter would.

Example:

InvoiceAdapter.get_invoice(invoice_number)

InvoiceAdapter.search_invoices(filters)

CustomerAdapter.get_customer_balance(customer_id)

ReportAdapter.generate_aging_report()

This means replacing the simulator with ERPNext or SAP later requires only a new adapter implementation.

Simulator Quality Checklist

Before considering the simulator complete, it should satisfy these criteria:

Every invoice belongs to a valid customer.
Every payment references a valid invoice.
Outstanding balances are mathematically correct.
Purchase orders and invoices are linked where appropriate.
Customer payment behavior is realistic.
Vendor payment behavior is realistic.
Intentional anomalies exist for testing.
Data generation is reproducible via seeds.
Multiple scenario packs are supported.
All business relationships are internally consistent.
One Major Improvement I'd Like to Add

While writing this chapter, I realized we can make the simulator even more powerful.

Instead of treating it as just a database, we should treat it as a Business World Simulator.

That means time should move forward.

For example:

Day 1

Invoice issued.

Day 30

Payment becomes due.

Day 45

Customer still hasn't paid.

Day 60

Payment reminder should now be recommended.

Day 90

Customer becomes high risk.

This transforms the simulator from a static dataset into a living business environment.

Eventually, we could advance the simulation one day at a time and watch the assistant respond to changing financial conditions.

Why I recommend postponing this feature

It's an incredibly valuable idea, but it also adds significant complexity.

For the MVP, I recommend building a static simulator first.

Once the assistant is consistently selecting the right tools and reasoning correctly, we can evolve it into a time-based simulation in a later version.

That staged approach keeps the MVP focused while leaving room for a much richer testing environment in the future.



Chapter 12 — Database Design
Purpose

The database is the single source of truth for the Finance Simulation Environment and the AI application's operational data.

The design has four primary goals:

Model a realistic finance organization.
Support efficient querying through business services.
Separate business data from AI application data.
Make future ERP integration straightforward.
Database Philosophy

The database should not be designed around AI.

It should be designed as though we were building an actual ERP.

The AI sits on top of the business system.

This distinction is important because it means the same backend could later power:

A web application
A mobile app
Scheduled jobs
APIs
The AI assistant

without changing the underlying data model.

High-Level Data Architecture

We will organize the database into three logical domains.

PostgreSQL
│
├── Finance Data
│
├── Application Data
│
└── Evaluation Data

Keeping these concerns separate makes maintenance and testing much easier.

Finance Data

This represents the fictional company's business information.

Core entities include:

Customers
Vendors
Invoices
Invoice Items
Purchase Orders
Purchase Order Items
Payments
Products
Employees
Departments
Expense Claims

These tables model the business itself.

Application Data

This stores information generated by the AI application.

Examples:

Conversations
Messages
Tool Executions
Sessions
Application Settings

This data belongs to the assistant, not the simulated company.

Evaluation Data

The evaluation framework deserves its own schema.

Examples:

Evaluation Runs
Evaluation Cases
Expected Results
Actual Results
Scores
Metrics

This allows us to track AI quality over time.

Proposed Schemas

Rather than placing everything into the default public schema, we'll use PostgreSQL schemas.

finance
application
evaluation

Example:

finance.customers

finance.invoices

application.conversations

evaluation.test_cases

This creates a clean separation and mirrors our architecture.

Finance Entity Relationships

At a high level:

Customer
    │
    ├──────────────┐
    ▼              │
Invoices           │
    │              │
    ▼              │
Payments           │
                   │
Vendor─────────────┘
    │
    ▼
Purchase Orders

Every financial transaction should be traceable.

Customer Entity

The customer table should represent organizations, not individuals.

Suggested fields:

Column	Purpose
id	Internal UUID
customer_code	Human-readable identifier
company_name	Business name
industry	Industry classification
payment_terms	Net 30, Net 60, etc.
credit_limit	Approved credit
status	Active / Inactive
created_at	Record creation

Notice what's not stored:

Outstanding balance

Balances should generally be calculated from invoices and payments to avoid inconsistent data. If we later denormalize for performance, we can introduce cached summaries with clear update rules.

Invoice Entity

This is the central table of the simulator.

Suggested fields:

Column	Purpose
id	UUID
invoice_number	Business identifier
customer_id	FK to customer
issue_date	Invoice date
due_date	Payment due
currency	ISO code
status	Draft / Issued / Paid / Overdue
total_amount	Invoice total

Invoice line items should be stored separately.

Invoice Items

Each invoice can contain multiple items.

Invoice

↓

Invoice Items

↓

Product

Fields:

quantity
unit_price
tax
discount
subtotal

This allows realistic invoice calculations.

Payments

Each payment references an invoice.

Important fields:

payment_date
payment_amount
payment_method
reference_number

Support:

Partial payments
Multiple payments per invoice
Full settlements

This reflects real accounting workflows.

Purchase Orders

Purchase orders should mirror how procurement systems operate.

Fields include:

PO number
Vendor
Status
Approval date
Total amount

Each purchase order also has line items.

Products

Products are shared across invoices and purchase orders.

Fields:

SKU
Name
Category
Unit price
Active flag

This avoids duplication and enables richer analytics.

Employees

For the MVP, employees mainly support ownership and audit trails.

Fields:

Employee ID
Name
Department
Role

Later, this table can support approvals, assignments, and AI personalization.

Application Tables

These tables support the assistant.

Conversations

Stores:

Conversation ID
Start time
Last activity
Session metadata
Messages

Stores each turn.

Fields:

Role (User / Assistant / System)
Content
Timestamp

This enables session replay and debugging.

Tool Executions

Every tool call should be logged.

Fields:

Tool name
Parameters
Execution time
Success/failure
Correlation to conversation

This is invaluable when diagnosing AI behavior.

Evaluation Tables

The evaluation system is a first-class citizen.

Example entities:

Evaluation Case
Prompt
Expected tool
Expected parameters
Expected outcome
Evaluation Run
Timestamp
Model version
Git commit
Overall score
Evaluation Result
Tool selected
Parameters extracted
Response quality
Pass/fail

This lets us compare changes over time and prevent regressions.

UUIDs vs Sequential IDs

I recommend:

UUIDs for internal primary keys.
Human-readable business identifiers for users.

Example:

Internal:

550e8400-e29b-41d4-a716-446655440000

Displayed to users:

INV-2026-001245

This mirrors real enterprise systems.

Indexing Strategy

Even though we're running locally, we should establish sensible indexes.

Likely candidates include:

Invoice number
Customer ID
Vendor ID
Due date
Status
Payment date
Conversation ID

We'll only add additional indexes when profiling shows a need.

Soft Deletes

Instead of permanently deleting finance records, use soft deletes where appropriate.

Example:

deleted_at TIMESTAMP NULL

This better reflects enterprise systems and simplifies debugging during development.

Seed Data Strategy

The database should never be populated manually.

Instead:

Generate Company

↓

Generate Customers

↓

Generate Vendors

↓

Generate Products

↓

Generate Purchase Orders

↓

Generate Invoices

↓

Generate Payments

↓

Introduce Test Scenarios

The generator becomes part of the codebase, ensuring every developer can create the same environment.

Database Principles

The database should satisfy these rules:

Business entities are normalized.
AI data is separated from finance data.
Evaluation data is isolated.
Business identifiers are human-friendly.
Internal identifiers use UUIDs.
Relationships are enforced with foreign keys.
Derived values are computed where practical rather than duplicated.
Seed data is reproducible.
The schema reflects a real business, not an AI experiment.
A Major Architectural Improvement

While writing this chapter, I realized there's one addition that will make the platform significantly more powerful:

Introduce an Event Layer

Instead of viewing the database as a passive storage system, treat important business changes as domain events.

Examples:

Invoice Created
Invoice Paid
Payment Received
Purchase Order Approved
Vendor Added
Expense Submitted

Initially, these events can simply be written to an application.events table.

In the future, they can power:

Background jobs
Notifications
AI proactive suggestions
Audit trails
Automation workflows

For the MVP, we don't need a full event-driven architecture or message broker. Simply capturing these events creates a strong foundation for future capabilities without adding much complexity.

End of Chapter 12

At this point, we have designed the data layer that supports both the Finance Simulation Environment and the AI assistant itself.

One Suggested Reordering Before We Continue

Originally, we planned to discuss the FastAPI backend next. I think there's a better sequence.

Before designing APIs and backend endpoints, we should define how the AI request actually flows through the system.




Chapter 13 — AI Request Lifecycle & Orchestration
Purpose

This chapter defines the complete execution lifecycle of every request processed by the AI Finance Assistant.

Rather than thinking of the assistant as a chatbot, we should think of it as an AI Operating System.

Every request follows the same deterministic pipeline.

This makes the assistant:

Predictable
Explainable
Testable
Observable
Easy to debug
High-Level Request Flow

Every request follows this lifecycle.

User
    │
    ▼
Frontend
    │
    ▼
FastAPI Request Handler
    │
    ▼
Session Manager
    │
    ▼
Conversation Memory
    │
    ▼
Prompt Builder
    │
    ▼
LLM Planner
    │
    ▼
Execution Planner
    │
    ▼
Tool Executor
    │
    ▼
Result Validator
    │
    ▼
LLM Response Generator
    │
    ▼
Logging & Evaluation
    │
    ▼
Frontend

Notice something important:

The LLM appears twice.

This is intentional.

Why Two LLM Calls?

Most AI applications use one LLM call.

We will use two logical phases:

Phase 1 — Planning

The model decides:

What does the user want?
Which tools are needed?
Which parameters should be used?
Is clarification required?

No user-facing response is generated yet.

Phase 2 — Response Generation

After tools finish executing,

the model receives verified structured data.

Only then does it generate the final answer.

Separating planning from explanation dramatically reduces hallucinations.

Complete Request Lifecycle
Step 1 — User Sends Message

Example:

Show customers that owe us more than $10,000.

Frontend sends:

{
  "conversation_id": "...",
  "message": "Show customers that owe us more than $10,000."
}

Nothing complicated happens here.

Step 2 — FastAPI Creates Request Context

FastAPI immediately creates a request context.

Example:

Request ID

Conversation ID

Timestamp

User Message

Current Session

This request context follows the request through every layer.

Everything becomes traceable.

Step 3 — Retrieve Conversation Memory

The Memory Manager retrieves only relevant information.

Not the entire conversation.

Instead:

Relevant examples:

Previous filters
Previous invoices
Previous customer references

Irrelevant discussion is ignored.

Example:

Current question:

Which ones are overdue?

Memory retrieves:

Assistant previously displayed:

ABC

XYZ

Northwind

Now "ones" makes sense.

Step 4 — Build AI Context

FastAPI now constructs the planning prompt.

The prompt contains:

System Prompt
Relevant Memory
User Message
Available Tool Registry
Current Date
Company Policies (if required)

Notice:

No database schema.

No SQL.

No repositories.

The model only knows business capabilities.

Step 5 — Planning LLM

Now the first LLM call begins.

The planner must answer five questions.

Question 1

What does the user want?

Example:

Intent:

Retrieve overdue customers.

Question 2

Is clarification required?

If yes:

Stop.

Return clarification.

Question 3

Which tools are needed?

Example:

get_overdue_invoices()

get_customer_balance()
Question 4

Can these tools run in parallel?

Example:

Invoice lookup

Customer lookup

can execute simultaneously.

Question 5

What parameters should be passed?

Example:

minimum_balance=10000

minimum_days=30

Planning ends here.

No natural language response has been produced yet.

Step 6 — Execution Plan

FastAPI converts the planning output into an execution graph.

Example:

Tool A

↓

Tool B

↓

Merge Results

↓

Continue

Or:

Tool A

Tool B

Tool C

↓

Parallel

↓

Merge

This execution graph belongs to FastAPI, not the LLM.

Step 7 — Parameter Validation

Before any tool executes:

Validate:

Required parameters
Parameter types
Allowed ranges
Business constraints

Example:

Bad:

days = -300

Rejected immediately.

The LLM should never bypass validation.

Step 8 — Tool Execution

FastAPI executes tools.

One important design principle:

The LLM never executes Python.

FastAPI owns execution.

Example:

get_overdue_invoices(days=60)

returns

JSON

No natural language.

Step 9 — Result Validation

Before results reach the model:

FastAPI validates:

JSON schema
Missing fields
Null values
Duplicate objects
Unexpected errors

If validation fails,

FastAPI handles the failure before involving the LLM.

Step 10 — Response LLM

Now the second LLM call begins.

Inputs:

Original question
Tool outputs
Conversation context

Responsibilities:

Explain
Summarize
Compare
Recommend
Format

No additional tool calls occur during this stage.

This separation keeps execution deterministic.

Step 11 — Store Memory

The Memory Manager stores:

User message
Assistant response
Tool calls
Important entities
Conversation summary (when appropriate)

This prepares the next interaction.

Step 12 — Evaluation Hook

Every completed request passes through the evaluation framework.

Metrics captured include:

Tool selection accuracy
Parameter extraction
Tool latency
Response latency
Hallucination detection (where applicable)
Groundedness
Conversation continuity

This enables continuous measurement during development.

Step 13 — Logging

Every request produces structured logs.

Example:

Request ID

Conversation ID

Prompt Version

Planner Output

Tools Selected

Execution Time

Tool Results

Response Time

Errors

Evaluation Score

These logs are essential for debugging and future optimization.

Step 14 — Response Returned

Frontend receives:

{
  "response": "...",
  "tool_summary": "...",
  "citations": [],
  "metadata": {
      "latency_ms": ...
  }
}

The frontend decides how to display the information.

Clarification Branch

Not every request proceeds to execution.

Example:

User:

Show invoices.

Planner decides:

Ambiguous.

Instead of executing tools:

Return:

Would you like all invoices, unpaid invoices, or overdue invoices?

Execution stops.

No unnecessary work occurs.

Error Recovery Branch

Example:

Database unavailable.

Planner already selected:

get_unpaid_invoices()

Tool execution fails.

Instead of crashing:

FastAPI returns structured failure information.

The Response LLM explains:

I couldn't retrieve invoice information because the Finance Simulator is currently unavailable.

The user receives a helpful explanation rather than a technical exception.

Parallel Execution

Suppose the user asks:

Show our cash position and our overdue receivables.

These are independent.

Execution graph:

Cash Position

         │

         ├──────► Merge

         │

Receivables

FastAPI should execute independent tools concurrently whenever possible to improve responsiveness.

Request State Machine

Every request moves through well-defined states.

Received

↓

Planning

↓

Validation

↓

Executing

↓

Reasoning

↓

Logging

↓

Completed

If something fails:

Executing

↓

Failed

↓

Recover

↓

Completed

Explicit states simplify monitoring and debugging.

Orchestration Principles

Every request must satisfy these rules:

FastAPI owns orchestration.
The planner never executes tools.
The responder never plans tools.
Tools return structured data only.
All inputs are validated before execution.
All outputs are validated before reasoning.
Memory retrieval is selective.
Every request is logged.
Every request is measurable.
Every request is reproducible using the same simulator seed and conversation history.
One Architectural Refinement

While writing this chapter, I identified one refinement that I believe will significantly improve maintainability:

Introduce a Workflow Engine Inside FastAPI

Rather than embedding the orchestration directly in the /chat endpoint, encapsulate it in a reusable workflow component.

Conceptually:

Chat Endpoint
      │
      ▼
FinanceAssistantWorkflow
      │
      ├── Memory Step
      ├── Planning Step
      ├── Validation Step
      ├── Tool Execution Step
      ├── Response Step
      ├── Logging Step
      └── Evaluation Step

Each step becomes an independent, testable unit with clear inputs and outputs.

Benefits:

Easier unit testing.
Simpler debugging.
Ability to reuse the workflow for APIs, CLI tools, or batch jobs.
Future workflows (e.g., HR Assistant, Procurement Assistant) can inherit the same orchestration framework and swap only the domain-specific tools.

This aligns perfectly with your long-term vision of building multiple AI employees on top of a shared AI orchestration platform.



Chapter 14 — FastAPI Backend Architecture
Purpose

This chapter defines the implementation architecture of the backend application.

The backend has four primary responsibilities:

Expose APIs to the frontend.
Orchestrate AI request execution.
Execute business tools safely.
Manage application state.

The backend should contain all business logic.

Neither the frontend nor the LLM should contain business rules.

Backend Philosophy

FastAPI is not an API layer.

It is the Application Runtime.

Think of it as an operating system for AI employees.

It manages:

AI reasoning
Workflow execution
Tool discovery
Conversation memory
Logging
Evaluation
Security
Configuration

Every request flows through FastAPI.

High-Level Backend Structure
backend/
│
├── app/
│
├── domains/
│
├── infrastructure/
│
├── ai/
│
├── workflows/
│
├── simulator/
│
├── evaluations/
│
├── tests/
│
└── scripts/

Notice something.

Finance is not the center of the project.

The AI platform is.

Finance is simply one domain.

Proposed Folder Structure
backend/

app/
│
├── api/
│
├── config/
│
├── middleware/
│
├── dependencies/
│
├── startup/
│
└── main.py

ai/
│
├── prompts/
├── planner/
├── responder/
├── memory/
├── models/
├── tool_registry/
└── evaluation/

domains/
│
├── finance/
│
├── shared/
│
└── future/
│
    ├── hr/
│
    ├── procurement/
│
    └── sales/

workflows/

infrastructure/

simulator/

tests/

The important observation:

Finance is isolated.

The AI runtime is reusable.

Application Layers

The backend consists of seven layers.

API

↓

Workflow

↓

AI

↓

Tool Layer

↓

Service Layer

↓

Repository Layer

↓

Database

Each layer has a single responsibility.

API Layer

Responsibilities:

Receive HTTP requests.
Validate payloads.
Authenticate users (future).
Start workflows.
Return responses.

Nothing more.

The API should never contain business logic.

Workflow Layer

This becomes the heart of the application.

Example workflows:

Finance Assistant

Health Check

Evaluation Runner

Seed Simulator

Generate Reports

Every workflow follows the same lifecycle.

Input

↓

Execute Steps

↓

Output
Workflow Steps

Each workflow consists of reusable steps.

Example:

Load Session

↓

Retrieve Memory

↓

Build Prompt

↓

Plan

↓

Execute Tools

↓

Generate Response

↓

Store Memory

↓

Evaluate

↓

Return

Each step becomes an independent class.

AI Layer

This layer contains everything related to reasoning.

Responsibilities:

Planner

Responder

Prompt Templates

Memory

Tool Registry

Model Clients

Evaluation

The rest of the application should not know which LLM provider is being used.

Infrastructure Layer

Infrastructure contains external integrations.

Examples:

PostgreSQL

Redis (future)

LLM APIs

Logging

Configuration

Filesystem

External ERP adapters (future)

This keeps third-party dependencies isolated.

Domain Layer

Every business capability belongs to a domain.

Example:

Finance

contains:

Services

Repositories

Entities

Validators

Policies

Later:

HR

will have the same structure.

Shared Layer

Some components belong to every domain.

Examples:

Money

Currency

Date utilities

Pagination

Validation

Audit models

These should live under a shared package rather than inside Finance.

Dependency Injection

Every component should receive its dependencies through injection.

Example:

Workflow

↓

Invoice Service

↓

Invoice Repository

Instead of creating objects manually inside classes, dependencies are provided by the application container.

Benefits:

Easier testing.
Replace implementations without changing business logic.
Cleaner separation of concerns.
Configuration

No magic values should exist in code.

Configuration belongs in dedicated settings.

Examples:

LLM Model

Database URL

Simulator Seed

Prompt Version

Logging Level

Evaluation Mode

Different environments can override these values without modifying source code.

Startup Process

When the application starts:

Load Configuration

↓

Connect Database

↓

Register Tools

↓

Load Prompt Templates

↓

Initialize Workflows

↓

Run Health Checks

↓

Accept Requests

Startup should fail fast if critical dependencies are unavailable.

Tool Registry Initialization

During startup, the backend discovers and registers available tools.

Each tool should provide:

Name
Description
Parameters
Return schema
Version
Domain

The AI planner reads only this registry.

It never inspects implementation details.

Request Models

Every API endpoint should use typed request and response models.

Example:

ChatRequest

↓

ChatResponse

↓

ToolExecutionResponse

↓

EvaluationResponse

This provides validation and clear API contracts.

Middleware

Middleware should handle cross-cutting concerns.

Examples:

Request IDs
Logging
Timing
Exception handling
CORS
Compression (future)

Business logic should never appear in middleware.

Exception Handling

Exceptions should be categorized.

Examples:

Validation Error

Business Rule Error

Infrastructure Error

AI Error

Each category should produce a consistent response format.

Logging

Every request should generate structured logs.

Capture:

Request ID
Conversation ID
Workflow
Planner output
Tool execution
Response latency
Errors

Avoid logging sensitive data if the platform later connects to real customers.

Background Jobs

Although the MVP focuses on interactive chat, the architecture should reserve a place for asynchronous work.

Examples:

Rebuilding evaluation datasets
Generating simulator data
Scheduled reports
Future notification tasks

Keeping these separate from request handling prevents long-running operations from blocking users.

Health Monitoring

The backend should expose internal health checks.

Examples:

Database connectivity
LLM availability
Simulator status
Tool registry loaded
Configuration validity

This makes troubleshooting much easier during development.

Testing Strategy

Every layer should be tested independently.

Layer	Test Type
API	Endpoint tests
Workflow	Workflow integration tests
AI Planner	Evaluation cases
Tool Layer	Unit tests
Services	Unit and integration tests
Repositories	Database integration tests
Simulator	Scenario validation tests

By isolating testing, failures become easier to diagnose.

Development Workflow

A typical development cycle should look like:

Implement Feature

↓

Write Unit Tests

↓

Run Integration Tests

↓

Run AI Evaluations

↓

Manual Chat Testing

↓

Merge

This sequence ensures that both deterministic logic and AI behavior are validated before changes are accepted.

Backend Design Principles

The backend should adhere to the following principles:

FastAPI orchestrates everything.
APIs remain thin.
Workflows coordinate execution.
Domains encapsulate business logic.
Infrastructure isolates external systems.
AI components remain provider-agnostic.
All configuration is externalized.
Every dependency is injectable.
Every request is observable.
Every component is independently testable.
Architectural Improvement: Introduce a Workflow SDK

One enhancement I recommend is introducing a small internal framework for defining workflows.

Instead of each workflow being implemented differently, define a common interface such as:

Workflow

↓

initialize()

↓

execute()

↓

cleanup()

Each workflow step would implement a standard contract.

Benefits include:

Consistent execution patterns.
Shared logging and metrics.
Easier onboarding for contributors.
Reusable orchestration across Finance, HR, Procurement, and future AI employees.

Over time, this could evolve into the core of your own AI orchestration framework.


Chapter 15 — Frontend Architecture (Next.js)
Purpose

The frontend provides the user interface for interacting with the AI Finance Assistant.

Unlike a traditional ERP, users do not navigate dozens of menus and forms.

Instead, the interface is centered around natural language, with structured UI components used when they improve clarity.

The frontend should remain:

Thin
Responsive
Stateless where practical
Focused on presentation

Business logic belongs entirely in the backend.

Frontend Philosophy

The frontend should never make business decisions.

It should not determine:

Which tools to call
Which invoices to retrieve
Which customer is high risk
How reports are calculated

Its responsibilities are limited to:

Capturing user input
Displaying responses
Rendering structured components
Managing client-side UI state

Everything else belongs to FastAPI.

High-Level Frontend Architecture
Browser
    │
    ▼
Next.js
    │
    ▼
Pages / App Router
    │
    ▼
UI Components
    │
    ▼
State Management
    │
    ▼
API Client
    │
    ▼
FastAPI Backend
Application Structure

A proposed project structure:

frontend/
│
├── app/
│
├── components/
│
├── features/
│
├── hooks/
│
├── lib/
│
├── services/
│
├── types/
│
├── styles/
│
└── tests/

This separates reusable UI from domain-specific functionality.

Pages

The MVP requires only a small number of pages.

/

Chat

Conversation History

Settings

Evaluation Dashboard (Developer Only)

Keep navigation intentionally minimal.

Primary Interface

The homepage is the assistant.

-----------------------------------

AI Finance Assistant

-----------------------------------

Conversation

Conversation

Conversation

-------------------------------

Message Input

-----------------------------------

The user should feel they are talking to a finance colleague rather than operating an ERP.

Core Components

The application should be composed of reusable UI components.

Examples:

ChatWindow

MessageBubble

MessageInput

ConversationSidebar

LoadingIndicator

ErrorBanner

TableRenderer

ChartRenderer

ToolStatus

MarkdownRenderer

Each component should have one responsibility.

Rich Response Rendering

The backend should return structured content, not only plain text.

For example, if the assistant returns unpaid invoices:

Instead of rendering:

"There are five unpaid invoices."

Render:

Response Summary

↓

Invoice Table

↓

Suggested Actions

The UI should automatically detect structured payloads and choose the best presentation.

Tables

Finance work is table-heavy.

The frontend should support reusable tables with:

Sorting
Pagination
Filtering
Copy to clipboard
CSV export (future)

The assistant should be able to answer in both prose and structured tables.

Charts

Initially, charts are optional.

However, the architecture should support future visualizations such as:

Aging buckets
Cash flow trends
Outstanding balances
Payment performance

The backend provides the data; the frontend decides how to render it.

Conversation Sidebar

The sidebar should display previous conversations.

Each conversation includes:

Title
Last activity
Date

Titles can be generated automatically from the first meaningful user request.

Message Rendering

Messages should support multiple content types.

Examples:

Plain text
Markdown
Tables
Lists
Code blocks (developer mode)
Error messages

This makes the interface flexible without requiring multiple pages.

Streaming Responses

The assistant should stream responses instead of waiting for the entire answer.

Benefits:

Faster perceived performance.
More natural interaction.
Easier cancellation of long responses.

The backend architecture should already support streaming so this can be enabled without major redesign.

Tool Execution Status

Although users should not see technical implementation details, they benefit from lightweight progress indicators.

For example:

Analyzing request...

Searching invoices...

Preparing summary...

Avoid exposing internal tool names or implementation-specific terminology.

Conversation State

The frontend maintains only UI-related state.

Examples:

Current conversation ID
Draft message
Sidebar visibility
Loading status
Theme

Business state remains on the backend.

State Management

For the MVP, keep state management simple.

Use:

Local component state where possible.
Shared client state only for cross-page UI concerns.

Avoid introducing unnecessary complexity until the application genuinely requires it.

API Layer

All communication with the backend should pass through a centralized API client.

Responsibilities:

HTTP requests
Authentication headers (future)
Error handling
Streaming support

Components should never make raw network requests directly.

Error Experience

Errors should be understandable.

Avoid:

Internal Server Error

Prefer:

I couldn't retrieve invoice information. Please try again.

The backend provides meaningful errors; the frontend presents them clearly.

Responsive Design

Although development targets desktop users, the layout should degrade gracefully on tablets and smaller screens.

Finance professionals often work on large monitors, so desktop remains the primary optimization target.

Accessibility

Basic accessibility should be considered from the beginning.

Examples:

Keyboard navigation.
Focus management.
Semantic HTML.
Screen-reader-friendly labels.

Building this in early is easier than retrofitting it later.

Developer Mode

Since you'll be actively developing and debugging the assistant, include a developer mode.

Possible features:

Request ID
Response latency
Planner output (optional)
Tool execution timeline
Evaluation score

This mode should be disabled in a production-facing environment but will be invaluable during development.

Frontend Testing

The frontend should be tested at multiple levels.

Layer	Test Type
Components	Unit tests
Pages	Integration tests
API Client	Mocked API tests
End-to-End	Full workflow tests

The goal is to verify both UI behavior and the overall user experience.

Design Principles

The frontend should follow these principles:

Chat is the primary interface.
Structured data should render as structured UI.
Business logic never lives in the frontend.
Components should have a single responsibility.
Responses should stream whenever possible.
State management should remain simple.
The backend is the source of truth.
The UI should remain fast and uncluttered.
Developer tooling should be built into the application.
The architecture should support richer interactions in future versions.
A Significant UX Improvement: AI Canvas

I believe there's one feature worth planning for now, even if we don't implement it in the MVP.

Instead of limiting the assistant to a chat window, introduce the concept of an AI Canvas.

Imagine the screen divided into two areas:

----------------------------------------------------
| Conversations | Chat                  | Canvas    |
|               |                       |           |
|               | User asks a question  | Table     |
|               |                       | Chart     |
|               | Assistant responds    | Report    |
|               |                       | Export    |
----------------------------------------------------

The chat remains the conversational interface, while the canvas displays persistent artifacts such as:

Invoice tables
Aging reports
Financial summaries
Charts
Downloadable reports

This avoids forcing users to scroll back through long conversations to find important information.

For the MVP, we can simply render these elements inline within the chat. However, designing the backend to return structured content rather than plain text means we can later introduce an AI Canvas with minimal architectural changes.



Chapter 16 — Development Roadmap & Milestones
Purpose

This chapter defines the implementation strategy for the AI Finance Assistant MVP.

The objective is not to build every feature immediately.

The objective is to maintain a working localhost application at every stage.

At the end of each milestone:

The application should run.
The assistant should be testable.
Existing functionality should continue to work.
Automated tests should pass.

We never allow the project to enter a "half-built" state.

Guiding Principle

Every milestone must satisfy one rule:

The application must always be demonstrable.

A smaller working system is more valuable than a larger broken system.

Development Strategy

Instead of implementing complete modules one at a time, we'll build complete vertical slices.

Each slice includes:

Frontend
Backend
AI
Database
Tests

For example:

User asks:

"Hello"

↓

Frontend sends request

↓

FastAPI receives request

↓

LLM responds

↓

Frontend displays response

Even though no finance functionality exists yet, the entire pipeline is operational.

Milestone 1 — Project Foundation
Goal

Create the project skeleton.

Deliverables

Frontend project

Backend project

Database connection

Configuration system

Logging

Docker (optional for local development)

CI pipeline

Git repository

README

Coding standards

At the end of this milestone:

Running:

npm run dev

and

uvicorn app.main:app --reload

should launch the full application.

No finance functionality exists yet.

Only infrastructure.

Milestone 2 — Basic AI Chat

Goal:

The assistant behaves like ChatGPT.

Features:

Chat UI
Conversation history
FastAPI endpoint
LLM integration
Streaming responses
Memory

No finance tools yet.

Example:

User:

Hello

Assistant:

Hello! How can I help you with your finances today?

Pipeline verified.

Milestone 3 — Tool Calling

Goal:

The assistant successfully calls one tool.

Only one.

Example tool:

get_current_date()

Conversation:

User:

What's today's date?

Planner

↓

Tool

↓

Response

This milestone proves:

The LLM can plan.

FastAPI can execute.

The tool registry works.

Milestone 4 — Finance Simulator

Goal:

Replace the toy tool.

Deliverables:

Customer table

Invoice table

Payment table

Seed generator

Sample data

The simulator now behaves like a tiny ERP.

Milestone 5 — First Finance Tool

Goal:

One real finance capability.

Tool:

get_unpaid_invoices()

Example:

User:

Show unpaid invoices.

Everything works.

End-to-end.

This becomes the first true demonstration of the product.

Milestone 6 — Core Finance Skills

Add:

Invoice search
Customer balance
Overdue invoices
Vendor balance

Now the assistant becomes useful.

Milestone 7 — Multi-Tool Reasoning

Goal:

The planner can combine tools.

Example:

User:

Which customers owe us over $10,000?

Execution:

Retrieve invoices

↓

Aggregate balances

↓

Return summary

The assistant now performs genuine reasoning.

Milestone 8 — Evaluation Framework

Goal:

Measure AI quality.

Introduce:

Evaluation datasets

Ground truth

Tool accuracy

Reasoning accuracy

Regression testing

Now every change can be measured objectively.

Milestone 9 — Advanced Finance Intelligence

Add:

Duplicate invoices

PO matching

Aging report

Risk scoring

Recommendation engine

The assistant now resembles a junior finance analyst.

Milestone 10 — MVP Complete

Deliverables:

Conversational finance assistant
Finance simulator
Evaluation framework
Full localhost workflow
CI pipeline
Documentation
Stable architecture

At this point:

We stop.

No deployment.

No cloud.

No production ERP.

Only a polished localhost MVP.

Continuous Testing Strategy

Testing is not postponed until the end.

Every milestone includes testing.

Feature

↓

Unit Tests

↓

Integration Tests

↓

AI Evaluation

↓

Manual Chat Testing

↓

Merge

This prevents large debugging sessions later.

Definition of Done

A milestone is complete only when all of the following are true:

Feature implemented.
Unit tests pass.
Integration tests pass.
AI evaluation passes.
Manual chat test succeeds.
Documentation updated.
CI pipeline passes.

No exceptions.

Branching Strategy

Use a simple Git workflow during MVP development.

main

↓

feature/tool-registry

↓

feature/invoice-search

↓

feature/memory

↓

feature/evaluation

Merge only after passing the Definition of Done.

Technical Debt Policy

Some shortcuts are acceptable during the MVP, but they must be documented.

Examples:

Acceptable:

Simple authentication placeholder.
Basic styling.
Hardcoded demo company branding.

Not acceptable:

Business logic in prompts.
SQL inside tools.
Frontend business logic.
Untested workflows.

This distinction keeps the architecture clean while allowing rapid progress.

Progress Tracking

Track progress at the capability level rather than the file level.

Example:

Capability	Status
Chat UI	✅
Planner	✅
Tool Registry	✅
Finance Simulator	🔄
Invoice Search	⏳
Duplicate Detection	⏳

This reflects business value rather than implementation details.

Success Criteria for the MVP

The MVP is successful if a finance user can naturally ask questions such as:

"Show unpaid invoices."
"Which customers owe us the most money?"
"Find duplicate invoices."
"Generate an aging report."
"Which invoices should I follow up on first?"

And the assistant consistently:

Understands the request.
Selects the correct tools.
Returns accurate information.
Explains its reasoning clearly.
Does not hallucinate business data.

If those outcomes are achieved reliably on localhost using the Finance Simulation Environment, the MVP has met its objective.

Architectural Improvement: Feature Flags

One enhancement I'd add before implementation begins is a lightweight feature flag system.

Examples:

AI_EVALUATION=true

STREAMING=true

DEVELOPER_MODE=true

EXPERIMENTAL_MULTI_TOOL=false

Feature flags allow you to:

Test new capabilities safely.
Compare different implementations.
Disable unstable features without changing code.
Keep the MVP stable while experimenting.

This will become increasingly valuable as the assistant grows in complexity.



Chapter 17 — Engineering Standards & Best Practices
Purpose

This chapter defines the engineering standards that govern the development of the AI Finance Assistant.

These standards ensure the project remains:

Maintainable
Modular
Testable
Consistent
Easy to extend
Easy for both humans and AI assistants to contribute to

If a proposed implementation conflicts with these standards, the standards take precedence.

Engineering Philosophy

The project follows a few core principles:

Correctness before cleverness.
Simplicity before abstraction.
Readability before brevity.
Explicit behavior over implicit behavior.
Deterministic systems over unpredictable systems.
Composition over duplication.
Small, testable units over large, complex modules.

Every design decision should reinforce these principles.

General Coding Standards

All code should be:

Typed where practical.
Self-explanatory.
Modular.
Documented when the intent is not obvious.
Consistent with the surrounding codebase.

Avoid:

Deeply nested logic.
Long functions.
Hidden side effects.
Unused code.
Premature optimization.
Python Standards

The backend should adopt modern Python practices.

Examples:

Use type hints consistently.
Prefer dataclasses or Pydantic models for structured data.
Keep functions focused on a single responsibility.
Favor descriptive names over abbreviations.

Target compatibility with a modern Python version and keep dependencies current but stable.

FastAPI Standards

FastAPI endpoints should:

Validate all inputs.
Return typed responses.
Remain thin.
Delegate work to workflows or services.

Endpoints should never contain:

SQL
Business rules
Prompt construction
Tool selection
Data transformation logic

They simply coordinate request handling.

Service Standards

Services encapsulate business logic.

Rules:

One service per business domain.
Services may collaborate with other services.
Services should remain independent of HTTP concerns.
Services should not know about the frontend.

Services become the reusable business layer.

Repository Standards

Repositories have one responsibility:

Access data.

Repositories should:

Read data.
Write data.
Map database objects.

Repositories should not:

Calculate business rules.
Perform AI reasoning.
Build responses.
Tool Standards

Every tool should:

Represent one business capability.
Return structured data.
Validate inputs.
Produce deterministic outputs.

Tools should not:

Execute SQL directly.
Generate user-facing prose.
Maintain conversation state.
Workflow Standards

Every workflow should follow the same lifecycle.

Initialize

↓

Validate

↓

Execute

↓

Log

↓

Evaluate

↓

Complete

No workflow should skip logging or evaluation.

AI Prompt Standards

Prompts should define:

Behavior.
Constraints.
Available tools.
Expected response style.

Prompts should not contain:

Business calculations.
Finance policies.
Hardcoded customer logic.

Those belong in deterministic code.

Prompt Versioning

Treat prompts like source code.

Every prompt should have:

Version
Author
Change history
Evaluation results

Prompt changes should trigger AI regression testing before being accepted.

Logging Standards

All logs should be structured.

Include:

Timestamp
Request ID
Conversation ID
Workflow
Severity
Component

Avoid free-form log messages that are difficult to search.

Error Handling Standards

Every error should fall into a known category.

Examples:

Validation
Business
Infrastructure
AI
Unexpected

Users receive friendly messages.

Developers receive detailed logs.

Testing Standards

Testing is mandatory.

Every new feature requires:

Unit tests.
Integration tests.
AI evaluation cases.

No feature is considered complete without automated validation.

Evaluation Standards

Every AI capability should have measurable success criteria.

Examples:

Correct tool selection.
Correct parameter extraction.
Correct use of conversation memory.
No hallucinated finance data.
Clear explanations.

Evaluation should be repeatable and automated.

Documentation Standards

Documentation should live alongside the code.

Each major component should explain:

Purpose.
Responsibilities.
Dependencies.
Usage.

Avoid documentation that merely restates code.

Instead, explain intent and architectural decisions.

Naming Conventions

Names should reflect business meaning.

Good examples:

InvoiceService
CustomerRepository
GenerateAgingReportWorkflow

Avoid vague names like:

Manager
Helper
Utils
Processor

Names should communicate purpose immediately.

Dependency Management

Every dependency should have a clear justification.

Before adding a new library, ask:

Does the standard library already solve this?
Can an existing dependency solve this?
Does this library reduce long-term complexity?

Prefer fewer, well-maintained dependencies.

Code Review Checklist

Before merging, verify:

Architecture is respected.
Single Responsibility Principle is maintained.
Tests pass.
AI evaluations pass.
Documentation updated.
Logging included where appropriate.
Errors handled consistently.
No unnecessary abstractions introduced.
AI-Assisted Development Standards

Because AI tools will contribute code, every AI-generated change should be reviewed against the same standards.

AI-generated code should:

Follow the project architecture.
Include tests where appropriate.
Avoid introducing hidden complexity.
Explain non-obvious design decisions in comments or documentation.
Never bypass established layers.

AI is treated as a contributor, not as an authority.

Definition of Production-Quality Code

Even though the MVP targets localhost, we should aim for production-quality engineering practices.

Production-quality code is:

Readable.
Tested.
Observable.
Deterministic.
Documented.
Modular.
Easy to replace.

The deployment environment can evolve later, but the engineering discipline should exist from the beginning.

Project Principles

The entire project can be summarized by the following principles:

FastAPI orchestrates the application.
The LLM reasons but does not execute.
Business logic lives in services.
Tools expose business capabilities.
Repositories isolate persistence.
The simulator models a real business.
The frontend remains a presentation layer.
Every capability is testable.
Every AI decision is measurable.
Architecture should enable future AI employees beyond Finance.
Final Recommendation: Create an Architecture Decision Record (ADR) Directory

One addition I'd strongly recommend is adopting Architecture Decision Records (ADRs) from the very beginning.

Create a directory such as:

docs/
└── adr/
    ├── 0001-fastapi-as-orchestrator.md
    ├── 0002-two-phase-llm-execution.md
    ├── 0003-finance-simulator.md
    ├── 0004-tool-registry.md
    └── ...

Each ADR should capture:

The decision.
The alternatives considered.
The rationale.
The consequences.

This provides a historical record of why important architectural choices were made. It becomes especially valuable as the project evolves or new contributors (human or AI) join.

End of Chapter 17
My Overall Assessment of the MVP

At this point, I think we've designed something larger than an AI Finance Assistant.

We've effectively designed an AI Employee Platform, with Finance as the first implementation.

The reusable pieces we've intentionally separated are:

AI orchestration engine
Workflow framework
Tool registry
Evaluation framework
Conversation memory
Backend platform
Frontend platform

Only the domain layer changes between Finance, HR, Procurement, Sales, and future assistants.

One architectural refinement before implementation

There is one thing I would change before writing any code.

Rather than naming the repository around finance (e.g., ai-finance-assistant), I would create a platform-oriented structure such as:

ai-employee-platform/
├── platform/
├── domains/
│   ├── finance/
│   ├── hr/
│   ├── procurement/
│   └── sales/
├── frontend/
├── backend/
└── docs/

The Finance Assistant then becomes the first domain implementation on top of a reusable AI platform.

That small naming and repository decision will make it much easier to grow this project into a family of AI employees without restructuring the codebase later. I believe it aligns perfectly with your long-term goal of building business AI assistants rather than a single-purpose finance chatbot.


# AI Finance Assistant — PRD/SDD Addendum
## Chapters 18–27: Finance Domain Expansion

Version: 1.1
Status: Draft
Scope: Extends the MVP from an invoice-centric assistant (AR/AP) to a complete
read-fetch-reason finance analyst covering eleven finance domains.

---

# Chapter 18 — Domain Expansion Strategy

## Purpose

Chapters 1–17 delivered an AI Finance Assistant capable of reasoning over invoices,
customers, vendors, and purchase orders.

That is a narrow slice of what a finance department actually does.

This chapter defines how the assistant grows from an accounts-receivable analyst
into a general finance analyst, without destabilizing the system that already works.

## The Problem With Invoice-Only Coverage

A finance employee does not only think about invoices.

In a single day, the same person may:

Approve an expense claim.
Reconcile a bank statement.
Check whether a department is over budget.
Forecast whether cash will cover next month's payroll.
Decide whether a customer deserves a higher credit limit.
Answer an auditor's question.

If the assistant cannot help with these, it is a reporting tool, not a colleague.

## The Eleven Target Domains

The assistant will be extended to cover the following domains.

Existing (Chapters 1–17):

Accounts Receivable
Accounts Payable
Purchase Orders
Basic Reporting

New (this addendum):

1. Expense Management
2. Credit Management
3. Cash Flow Forecasting
4. Financial Planning & Analysis (Budgets)
5. Bank Reconciliation
6. Fixed Assets & Depreciation
7. Payroll Analysis
8. Procurement & Requisitions
9. Financial Close Management
10. Tax & Compliance Reporting
11. Audit Support & Internal Controls

## Scope Boundary — Read, Fetch, Reason

Every new capability in this addendum is strictly read-only.

The assistant may:

Retrieve data.
Apply deterministic business rules.
Reason over the results.
Explain conclusions.
Recommend actions.

The assistant may NOT:

Create records.
Modify records.
Approve anything.
Execute payments.
Send communications.

Write operations remain out of scope until an approval-and-audit workflow layer is
designed. Recommendation is permitted; execution is not.

This preserves the principle established in Chapter 2:

Reasoning always comes before execution.

## The Tool Budget Problem

Chapter 10 established that a larger toolset does not produce a smarter assistant.

Exposing too many tools increases:

Reasoning complexity.
Tool selection errors.
Latency.
Maintenance cost.

The existing MVP exposes roughly fifteen tools.

The eleven new domains would add approximately thirty-five more.

At fifty tools, naive tool exposure will degrade planning accuracy, particularly on
smaller models. Several tools will overlap semantically. "Show department spending"
could plausibly map to an expense tool, a budget tool, or a payroll tool.

Two mitigations are mandatory.

## Mitigation 1 — Semantic Distinctness

Every tool description must state, explicitly:

What the tool returns.
What question it answers.
What it does NOT do, when a sibling tool is easily confused with it.

Example:

get_expense_claims — Returns individual employee expense claim records
(travel, meals, supplies). Does NOT return departmental budget performance;
use get_budget_variance for that.

Tool descriptions are prompt engineering artifacts. They are versioned like prompts.

## Mitigation 2 — Domain Routing

Chapter 24 defines a domain router: a lightweight classification step that narrows
the tool set presented to the planner.

Routing is introduced only when measured tool-selection accuracy justifies it.

The decision is data-driven, not speculative. The evaluation framework decides.

## LLM Provider Constraints

The assistant runs on the Groq API.

Groq provides very low latency, which materially improves the two-phase pipeline
(two sequential LLM calls per request). However, the models available are generally
smaller than frontier models and are more sensitive to:

Large tool sets.
Ambiguous tool descriptions.
Loosely specified parameter schemas.
Unstructured planning output.

Three requirements follow.

Planning output must be strictly structured. Phase 1 must return machine-parseable
JSON conforming to a schema, validated before execution, with a bounded retry on
parse failure.

Parameter schemas must be tight. Prefer enums over free strings. Prefer explicit
date ranges over natural-language dates resolved by the model. Where the model must
resolve a relative date ("last quarter"), a deterministic date-resolution tool
should do the arithmetic.

Every domain addition must be measured. Tool-selection accuracy is recorded before
and after each domain is added. A regression is a blocking defect.

## Phased Delivery

The eleven domains are delivered in three phases, ordered by schema cost and risk.

Phase A — No new schema required. Data already exists in the simulator.

Expense Management
Credit Management
Cash Flow Forecasting

Phase B — One new entity group each.

Financial Planning & Analysis (budgets)
Bank Reconciliation (bank transactions)
Fixed Assets (assets and depreciation)

Phase C — Heavier modeling and higher risk.

Payroll Analysis
Procurement & Requisitions
Financial Close Management
Tax & Compliance Reporting
Audit Support & Internal Controls

Each phase must end in a demonstrable, fully evaluated application. The rule from
Chapter 16 is unchanged: a smaller working system is more valuable than a larger
broken system.

## Success Criteria for the Expansion

The expansion is successful when:

A finance employee can ask a question from any of the eleven domains and receive an
accurate, explained answer.

Tool-selection accuracy across the full suite remains at or above the accuracy
measured before the expansion began.

No hallucinated financial figures appear in any evaluation case.

Every domain has at least five evaluation cases, including one hallucination trap.

The assistant correctly refuses write requests and explains what it can do instead.

---

# Chapter 19 — Finance Simulation Environment v2

## Purpose

The simulator described in Chapter 11 models a company that only issues invoices and
receives payments.

A real company also pays salaries, holds bank accounts, sets budgets, owns equipment,
approves expenses, raises purchase requisitions, closes its books monthly, and files
tax returns.

The simulator must be extended so that Northwind Manufacturing Ltd. behaves like a
complete business.

## Design Philosophy (Unchanged)

Every record must belong to a believable business story.

The assistant must never be able to detect that it is talking to a simulator.

Data must be internally consistent, deterministic, and repeatable from a fixed seed.

## The Expanded Company

Northwind Manufacturing Ltd. now has:

Departments with annual and monthly budgets.
Employees with salaries, grades, and departments.
Bank accounts with transaction histories.
Fixed assets with depreciation schedules.
Expense claims submitted by employees against departments.
Purchase requisitions that precede purchase orders.
Monthly financial close checklists.
Tax registrations and periodic tax positions.
Approval and creation metadata on financial transactions.

## Consistency Invariants

The simulator seed is only valid if every invariant below holds. A consistency check
script must assert all of them.

Existing invariants (Chapter 11) remain in force:

Every invoice belongs to a real customer.
Every purchase order belongs to a real vendor.
Invoice balance equals total minus the sum of applied payments.
Overdue status agrees with due dates and the simulation date.

New invariants:

Every expense claim belongs to a real employee and a real department.
Approved expense claims must have an approver who is not the claimant.
Every bank transaction either matches a recorded payment, matches a payroll run,
represents a known bank fee or interest line, or is deliberately unmatched to create
reconciliation work.
The proportion of deliberately unmatched bank transactions is fixed and known, so
reconciliation tools have a verifiable expected answer.
Every department budget line has actual spend derived from real transactions
(expenses, purchase orders, payroll), not from random numbers.
At least two departments must be over budget and at least one materially under
budget, so variance analysis has something meaningful to explain.
Every fixed asset has a purchase date, cost, useful life, depreciation method, and a
computed accumulated depreciation consistent with the simulation date.
Every payroll run sums to the salaries of active employees for that period, plus
overtime and deductions, and appears as a matching bank transaction.
Every purchase order traces back to an approved purchase requisition, except for a
small, deliberate set of maverick purchase orders raised without requisitions, which
exist to give audit and control tools something to find.
Tax positions must be derivable from the underlying invoices and vendor payments,
not stored as independent random values.
Every financial close period has a checklist with a mix of completed, in-progress,
and blocked tasks for at least one open period.

## Deliberate Anomalies

The simulator must contain planted anomalies. Without them, analytical tools cannot
be validated and evaluation cases cannot assert non-trivial answers.

Required planted anomalies:

Duplicate invoices (already present).
Expense claims that exceed policy limits.
Expense claims submitted more than a set number of days after the expense date.
At least one expense claim approved by the claimant themselves.
Bank transactions with no matching internal record.
Internal payments with no matching bank transaction.
Purchase orders raised without a requisition.
Purchase orders where the same product is bought from multiple vendors at materially
different unit prices.
Customers whose payment behavior deteriorated over time.
A department that overspent its budget in a specific category.
Fully depreciated assets still recorded as in use.
A payment above the approval threshold with no recorded approver.

Every planted anomaly must be recorded in a machine-readable expectations file
generated at seed time. Evaluation cases reference this file so that expected answers
remain correct whenever the seed changes.

## Company Policies

Chapter 11 mentions company policies. They now become explicit, structured, and
queryable data — not prose inside a prompt.

Policies stored as structured records include:

Expense limits by category and employee grade.
Receipt requirements by amount threshold.
Expense submission deadlines.
Approval thresholds for expenses, purchase requisitions, and payments.
Standard customer payment terms and credit limits.
Standard vendor payment terms.
Depreciation methods and useful lives by asset class.
Tax rates by jurisdiction and category.

Policies live in the database. Business rules that apply them live in services.
Neither lives in a prompt. This preserves Chapter 17's rule that prompts must not
contain finance policies.

## Simulation Date

Reports, aging, depreciation, overdue status, and close periods all depend on "today."

A single configurable simulation date governs all of them.

The seed generator and every service must derive time-dependent values from this
date, never from an implicit system clock inside business logic. This keeps
evaluation cases stable over time.

## Seed Scale

The seed should be large enough to be realistic and small enough to reason about.

Target scale:

Departments: 6–8
Employees: 40–60
Customers: 25 (existing)
Vendors: 15 (existing)
Invoices: 200+ (existing)
Purchase requisitions: 60–80
Purchase orders: 40+ (existing)
Expense claims: 250–350 across 18 months
Bank accounts: 2–3
Bank transactions: 600–900 across 18 months
Budget lines: department × category × month for 18 months
Fixed assets: 40–60
Payroll runs: 18 monthly runs
Close periods: 18, with the most recent one open
Tax periods: 6 quarterly positions

---

# Chapter 20 — Database Design Extensions

## Purpose

Chapter 12 established three PostgreSQL schemas: finance, application, evaluation.

This chapter extends the finance schema. The application and evaluation schemas are
unchanged.

## Design Rules (Unchanged)

The database is designed as if we were building a real ERP, not as if we were
building an AI application.

The LLM never sees table names.

Repositories access data. Services apply rules. Tools expose capabilities.

## Phase A — No New Tables

Expense Management uses the existing expense_claims table, extended with the columns
required by policy checking.

Credit Management is derived entirely from existing customers, invoices, and payments.

Cash Flow Forecasting is derived entirely from existing invoices, purchase orders,
payments, and (once Phase C lands) payroll.

Columns to add to expense_claims:

employee_id, department_id, category, expense_date, submitted_date, amount, currency,
description, receipt_attached, status, approver_id, approved_date, policy_violations.

## Phase B — New Entity Groups

Budgets.

budgets: department_id, fiscal_year, category, period (month), budgeted_amount.
Actuals are never stored. They are always computed from real transactions, so that
variance can never drift out of sync with reality.

Bank.

bank_accounts: account_name, bank_name, account_number_masked, currency,
opening_balance, opening_date.

bank_transactions: bank_account_id, transaction_date, description, reference, amount
(signed), transaction_type, matched_payment_id (nullable), matched_payroll_run_id
(nullable), match_status.

Match status must be derivable. The reconciliation service must be able to recompute
matches deterministically; stored matches exist only as the record of the seeded
truth.

Fixed Assets.

fixed_assets: asset_tag, name, asset_class, department_id, vendor_id, purchase_date,
purchase_cost, useful_life_months, depreciation_method, salvage_value, status,
disposal_date, disposal_proceeds.

Accumulated depreciation and net book value are computed by a service from the
simulation date. They are not stored.

## Phase C — Heavier Modeling

Payroll.

payroll_runs: period, run_date, status, total_gross, total_deductions, total_net,
bank_transaction_id.

payroll_lines: payroll_run_id, employee_id, base_salary, overtime, bonus,
tax_withheld, other_deductions, net_pay.

employees is extended with: grade, salary, hire_date, termination_date, manager_id,
department_id, status.

Procurement.

purchase_requisitions: requisition_number, requester_employee_id, department_id,
requested_date, needed_by_date, justification, estimated_amount, status,
approver_id, approved_date.

requisition_items: requisition_id, product_id, quantity, estimated_unit_price.

purchase_orders is extended with: requisition_id (nullable — deliberately null for
maverick purchase orders), created_by_employee_id, approved_by_employee_id.

Financial Close.

close_periods: period, status (open, in_progress, closed), opened_date, closed_date.

close_tasks: close_period_id, task_name, category, owner_employee_id, status, due_date,
completed_date, blocking_reason.

Tax.

tax_rates: jurisdiction, category, rate, effective_from, effective_to.

tax_periods: jurisdiction, period, status, filing_due_date, filed_date.

Tax positions (collected, paid, net payable) are computed from invoices and vendor
payments by a service, never stored as free-standing values.

Audit and Controls.

No dedicated tables. Audit capabilities are derived from approval and creation
metadata added across transactional tables:

created_by_employee_id and approved_by_employee_id on invoices, payments, expense
claims, purchase requisitions, and purchase orders.

This is what makes segregation-of-duties analysis possible: the assistant can find
transactions where the creator and approver are the same person, or where an approval
was missing above a threshold.

## Indexing

Every column used as a common filter must be indexed:

Status columns, date columns, foreign keys, department_id, employee_id, category.

Analytical tools scan far more rows than lookup tools. Indexing is a functional
requirement, not an optimization.

---

# Chapter 21 — Phase A Domains

## Domain 1 — Expense Management

### Business Context

Employees submit claims. Finance checks them against policy. Managers approve or
reject. Finance reimburses.

The manual pain is policy checking at volume, and spotting duplicates or late
submissions.

### Capabilities

get_expense_claims(employee_id?, department_id?, status?, category?, date_from?,
date_to?, minimum_amount?)

Returns individual expense claim records with policy-violation flags.

get_pending_expense_approvals(department_id?, older_than_days?)

Returns claims awaiting approval, highlighting those waiting longest.

get_expense_policy_violations(department_id?, date_from?, date_to?)

Returns claims that breach a policy: over category limit, missing required receipt,
submitted after the deadline, or self-approved. The violation rules are deterministic
and live in the service layer.

get_expense_summary_by_department(date_from?, date_to?, category?)

Returns aggregated spend by department and category.

find_duplicate_expense_claims(employee_id?, date_from?, date_to?)

Detects likely duplicate claims: same employee, same or near-identical amount, same
category, within a small date window. Deterministic heuristic, service layer only.

### Reasoning Examples

Which expense claims are still waiting for approval?
Show claims that break our travel policy this quarter.
How much did Sales spend on travel last month?
Is anyone submitting duplicate claims?

## Domain 2 — Credit Management

### Business Context

Before extending terms or a higher credit limit, finance assesses a customer's
payment behavior and current exposure.

All of this is derivable from data the simulator already has.

### Capabilities

get_customer_payment_behavior(customer_id)

Returns average days-to-pay, payment reliability trend over time, count of late
payments, longest delay, and whether behavior is improving or deteriorating.

get_credit_exposure(customer_id?)

Returns current outstanding balance versus credit limit, utilization percentage, and
whether the limit is exceeded.

list_customers_over_credit_limit()

Returns all customers whose exposure exceeds their approved limit.

assess_credit_risk(customer_id)

Returns a structured risk profile combining exposure, payment behavior, invoice
history, and disputes. The tool returns evidence and deterministic risk indicators.
It does NOT return a recommendation — the assistant reasons over the evidence and
recommends in Phase 2. This is a deliberate architectural boundary: judgment belongs
to the reasoning layer, facts belong to tools.

### Reasoning Examples

Should we increase ABC Industries' credit limit?
Which customers are over their credit limit?
Is XYZ Corp paying slower than they used to?

## Domain 3 — Cash Flow Forecasting

### Business Context

The existing get_cash_position tool answers "what do we have now."

Finance needs "what will we have, and can we cover what's coming."

### Capabilities

get_expected_inflows(date_from, date_to)

Returns expected customer receipts in the window, based on unpaid invoices and their
due dates, adjusted by each customer's historical payment behavior. The adjustment
rule is deterministic and documented in the service.

get_expected_outflows(date_from, date_to)

Returns expected payments out: vendor invoices due, approved requisitions and open
purchase orders, scheduled payroll (once Phase C lands), and recurring costs.

forecast_cash_flow(weeks)

Returns a period-by-period projection of opening balance, inflows, outflows, and
closing balance.

get_payment_prioritization()

Returns the data needed to decide which vendor invoices to pay first: due dates,
payment terms, early-payment discounts, vendor criticality, and available cash. The
tool ranks by deterministic criteria; the assistant explains the trade-offs.

### Reasoning Examples

Will we have enough cash to cover next month?
What's our 8-week cash forecast?
Which vendor invoices should I pay first this week?
What happens to our cash if ABC pays late again?

---

# Chapter 22 — Phase B Domains

## Domain 4 — Financial Planning & Analysis (Budgets)

### Business Context

Managers ask two questions constantly: are we on budget, and if not, why.

Actuals must always be computed from transactions. Never stored. A stored actual is a
number that will eventually disagree with the underlying data.

### Capabilities

get_budget_vs_actual(department_id?, category?, period?, fiscal_year?)

Returns budgeted amount, computed actual, variance in currency, and variance as a
percentage.

get_budget_variance_analysis(department_id?, period?)

Returns the largest variances with their contributing transactions, so the assistant
can explain WHY a variance exists rather than merely reporting that it exists. This
is the difference between a report and an analyst.

get_department_spending(department_id?, date_from?, date_to?, category?)

Returns actual spend broken down by category and source (expenses, purchase orders,
payroll).

compare_periods(metric, period_a, period_b, department_id?)

Returns a like-for-like comparison of a metric across two periods.

### Reasoning Examples

Which departments are over budget?
Why is Marketing 20% over budget this quarter?
Compare Q2 spend to Q1.
What's driving the increase in operations costs?

## Domain 5 — Bank Reconciliation

### Business Context

Finance matches internal payment records to actual bank transactions. Mismatches mean
missing payments, unrecorded fees, or errors.

### Capabilities

get_bank_transactions(bank_account_id?, date_from?, date_to?, match_status?,
minimum_amount?)

Returns bank statement lines.

get_unreconciled_transactions(bank_account_id?, date_from?, date_to?)

Returns bank transactions with no matching internal record, and internal payments
with no matching bank transaction. Both directions matter.

reconcile_bank_account(bank_account_id, period)

Runs the deterministic matching algorithm (amount, date proximity, reference) and
returns matched items, unmatched items in both directions, and the resulting
discrepancy total.

explain_balance_difference(bank_account_id, period)

Returns the itemized components of the difference between the bank balance and the
internal ledger balance: timing differences, unrecorded fees, unmatched items.

### Reasoning Examples

Why doesn't our bank balance match the ledger?
Which bank transactions don't match any recorded payment?
Reconcile the main account for June.

## Domain 6 — Fixed Assets & Depreciation

### Business Context

Companies track equipment cost, depreciation, and book value.

Depreciation is computed, not stored. The service computes it from the simulation
date, the depreciation method, and the useful life.

### Capabilities

get_fixed_assets(asset_class?, department_id?, status?)

Returns the asset register with computed accumulated depreciation and net book value.

get_depreciation_schedule(asset_id?, period?)

Returns period-by-period depreciation for an asset or for the whole register.

get_asset_book_value(asset_id_or_class)

Returns current net book value.

find_fully_depreciated_assets(still_in_use_only?)

Returns assets whose accumulated depreciation has reached cost minus salvage value —
a common source of accounting cleanup work, and a planted anomaly in the simulator.

### Reasoning Examples

What's the book value of our IT equipment?
Which assets are fully depreciated but still in use?
How much depreciation will we book this quarter?

---

# Chapter 23 — Phase C Domains

## Domain 7 — Payroll Analysis

### Business Context

Payroll execution belongs to a payroll system. Payroll *analysis* belongs to finance,
and it is asked about constantly.

This domain is read-only and analytical. The assistant never runs payroll.

### Capabilities

get_payroll_summary(period?, department_id?)

Returns gross, deductions, and net totals by period and department.

get_payroll_cost_by_department(period?, fiscal_year?)

Returns headcount cost by department, with comparison to prior periods.

get_headcount(department_id?, as_of_date?)

Returns active headcount, joiners, and leavers.

get_overtime_analysis(department_id?, period?)

Returns overtime cost and the employees or departments driving it.

### Accuracy Requirement

Payroll figures are sensitive. Phase 2 must state the period and scope of every
payroll figure it reports, and must never aggregate across periods unless the tool
returned an aggregate. Individual salary disclosure is limited to what the tool
returns; the assistant must not infer or estimate individual pay.

## Domain 8 — Procurement & Requisitions

### Business Context

Before a purchase order exists, someone requests a purchase and someone approves it.

Weak procurement control shows up as maverick spend: purchase orders with no
requisition, or the same product bought from different vendors at different prices.

### Capabilities

get_purchase_requisitions(department_id?, status?, requester_id?, date_from?,
date_to?)

Returns requisitions with their approval state.

get_pending_requisition_approvals(older_than_days?)

Returns requisitions stuck in approval, sorted by age.

get_vendor_performance(vendor_id?)

Returns on-time delivery rate, price consistency, invoice accuracy (disputes and
duplicates), and order volume.

compare_vendor_pricing(product_id)

Returns the unit prices paid to different vendors for the same product, exposing
price inconsistency.

find_maverick_purchase_orders(date_from?, date_to?)

Returns purchase orders raised without an approved requisition.

### Reasoning Examples

Which requisitions are stuck in approval?
Are we buying the same product from multiple vendors at different prices?
Which vendors deliver late most often?

## Domain 9 — Financial Close Management

### Business Context

Month-end close is the largest recurring grind in finance. Teams work through a
checklist under time pressure and constantly ask: what's left, and what's blocking us.

### Capabilities

get_close_status(period?)

Returns the state of a close period: open, in progress, or closed, with completion
percentage.

get_open_close_tasks(period?, owner_id?, category?)

Returns outstanding tasks with owners, due dates, and blocking reasons.

get_close_blockers(period?)

Returns only the tasks that are blocked, with their stated reasons and what they are
blocking.

check_period_readiness(period)

Runs deterministic readiness checks: unposted invoices, unreconciled bank accounts,
unapproved expense claims, incomplete tasks. Returns a structured readiness report.

### Reasoning Examples

What's still open for June close?
Are we ready to close the books?
What's blocking the close?

## Domain 10 — Tax & Compliance Reporting

### Business Context

Finance must know how much tax was collected on sales, how much was paid on
purchases, what the net position is, and when filings are due.

### Capabilities

get_tax_summary(jurisdiction?, period?)

Returns tax collected on sales, tax paid on purchases, and net payable or
recoverable, computed from underlying invoices.

get_tax_filing_status(jurisdiction?, fiscal_year?)

Returns filing periods, due dates, and whether each has been filed.

get_taxable_transactions(jurisdiction?, period?, category?)

Returns the underlying transactions that make up a tax position, so the figure is
auditable and explainable.

### Accuracy Requirement

Tax figures carry regulatory consequence.

Phase 2 must present tax figures with their period, jurisdiction, and basis of
computation, and must state that figures are derived from the recorded transactions
and are not a substitute for a filed return. The assistant must never estimate a tax
figure that the tool did not return.

## Domain 11 — Audit Support & Internal Controls

### Business Context

Auditors and controllers ask control questions that take finance teams days to answer
manually.

This domain is where the assistant's value is most visible, because the answers are
tedious to produce and important to get right.

### Capabilities

get_transaction_audit_trail(entity_type, entity_id)

Returns who created a transaction, who approved it, and when.

find_segregation_of_duties_violations(date_from?, date_to?)

Returns transactions where the creator and the approver are the same person.

find_missing_approvals(threshold_amount?, date_from?, date_to?)

Returns transactions above an approval threshold with no recorded approver.

find_unusual_transactions(date_from?, date_to?)

Returns transactions that breach deterministic control rules: round-number amounts
above a threshold, payments just below an approval threshold, weekend or
out-of-hours postings, or amounts far outside a vendor's historical range. The rules
are explicit, documented, and deterministic. This is not anomaly detection by the
model; it is rule-based control testing, explained by the model.

get_control_exceptions_summary(period?)

Returns a consolidated summary of all control exceptions for a period.

### Reasoning Examples

Show all payments over ten thousand without a matching purchase order.
Did anyone approve their own expense claim?
Which transactions look unusual this quarter?

---

# Chapter 24 — Tool Selection at Scale

## Purpose

The assistant will expose roughly fifty tools once the expansion is complete.

Chapter 10 warned that large tool sets degrade planning. This chapter defines how to
detect and correct that degradation.

## The Baseline Rule

Before any domain is added, tool-selection accuracy is measured on the existing
evaluation suite and recorded.

After the domain is added, accuracy is measured again on the full suite.

A drop in accuracy on previously passing cases is a regression and must be fixed
before the milestone is accepted.

The evaluation framework is the gate. Not judgment. Not demonstration.

## Failure Mode 1 — Semantic Collision

Two tools answer superficially similar questions.

Example collisions to expect:

get_expense_summary_by_department versus get_department_spending versus
get_budget_vs_actual.

get_cash_position versus forecast_cash_flow.

get_expense_claims versus get_expense_policy_violations.

Mitigation: tool descriptions must include an explicit disambiguation clause naming
the sibling tool and the distinction. Descriptions are versioned artifacts and are
regression-tested like prompts.

## Failure Mode 2 — Planner Overload

The planner receives too many tool specifications and selects poorly, or times out.

Mitigation: domain routing.

## Domain Routing Architecture

Routing inserts one lightweight step before Phase 1 planning.

User message
    ↓
Domain Router (fast, cheap classification)
    ↓
Selected domain(s): e.g. [expenses, budgets]
    ↓
Phase 1 Planner — receives only the tools from the selected domains, plus a small
set of always-available cross-domain tools
    ↓
Tool Executor (unchanged)
    ↓
Phase 2 Response Generator (unchanged)

Design rules:

The router may select more than one domain. Cross-domain questions are common
("can we afford next month's payroll" spans cash flow and payroll).

The router must be permissive. When uncertain, it returns more domains rather than
fewer. A false narrow is a failed answer; a false wide is only slightly slower.

Always-available tools (date resolution, customer and vendor lookup) are never routed
away.

Routing is an optimization, not a semantic layer. If routing is removed, the system
must still work — only more slowly and less accurately.

Routing is introduced only when evaluation shows it is needed. It is designed in
advance so that adopting it is a configuration change, not a rewrite.

## Structured Planning Output

Given a smaller LLM, planning output must be strictly constrained.

The planner returns one of exactly three structured shapes:

A clarification request.
An ordered list of tool calls with validated parameters.
A direct answer, for conversational messages requiring no data.

Any output that fails schema validation triggers one bounded retry with an explicit
error message. A second failure returns a graceful clarification to the user. The
system never guesses on behalf of the model.

## Deterministic Date Resolution

Relative dates ("last quarter," "this month," "year to date") must not be resolved by
the model.

A resolve_date_range(expression) tool performs the arithmetic against the simulation
date and returns explicit start and end dates.

This removes an entire class of silent parameter errors.

---

# Chapter 25 — Evaluation Expansion

## Purpose

Chapter 8 of the roadmap established the evaluation framework.

The expansion multiplies the surface area the framework must cover.

## Coverage Requirements

Every domain must have, at minimum:

Five phrasing-variation cases (the same intent expressed five different ways).
Two parameter-extraction cases (dates, amounts, names, enums).
One ambiguity case that must produce a clarifying question.
One hallucination trap.
One cross-domain reasoning case.

Eleven domains therefore add at least one hundred evaluation cases.

## Metrics

The scorecard must report, per domain and overall:

Tool-selection accuracy.
Parameter-extraction accuracy.
Clarification appropriateness (asked when it should, did not ask when it should not).
Hallucination rate (any figure in the answer absent from tool output).
Memory usage accuracy (follow-up reference resolution).
Refusal correctness (write requests declined and explained).
Latency, per phase.

## Expectations Are Derived, Not Hardcoded

Expected answers must be derived from the seed expectations file produced by the
simulator (Chapter 19), not hardcoded into the evaluation cases.

If the seed changes, expectations regenerate. Evaluation cases remain valid.

Hardcoded expected values are technical debt that silently rots.

## Hallucination Traps

Every domain requires at least one trap. Examples:

Ask about an expense claim ID that does not exist.
Ask for the budget of a department that has no budget line.
Ask for a bank reconciliation for a period with no transactions.
Ask for the tax position of a jurisdiction the company is not registered in.
Ask for payroll for a future period.

The correct behavior in every case is an honest statement that the data does not
exist. Any invented figure is a failing result, regardless of how plausible it is.

## Regression Gate

The evaluation suite runs in CI.

A pull request that reduces tool-selection accuracy, raises hallucination rate, or
breaks a previously passing case cannot be merged.

Prompt changes and tool-description changes are treated identically to code changes.

---

# Chapter 26 — Guardrails for the Expanded Assistant

## Read-Only Enforcement

The expanded assistant handles payroll, tax, and audit data. The blast radius of a
mistaken action is much larger than it was for invoice queries.

Enforcement is architectural, not merely instructional:

No tool in the registry performs a write operation.
The repository layer used by tools exposes read methods only.
A registry-level assertion fails the application at startup if any registered tool
declares a write capability.

Prompt instructions are the last line of defense, not the first.

## Refusal Behavior

When a user requests an action the assistant cannot take ("approve this claim,"
"pay this invoice," "file the return"), the assistant must:

Decline clearly.
Explain that it can analyze and recommend but not execute.
Offer the analysis that supports the action.

Never invent a capability. Chapter 3, Principle 2 is unchanged: if a capability does
not exist as a tool, it does not exist.

## Sensitive Domain Handling

Payroll, tax, and audit answers must always state:

The period covered.
The scope (which department, jurisdiction, or entity).
That figures are derived from recorded transactions.

The assistant must never estimate, extrapolate, or fill a gap in these domains. If
the tool returned no data, the answer is that there is no data.

## Data Minimization

Individual salary information is returned only when the question is explicitly about
an individual and the tool returns it. Aggregate questions receive aggregate answers.

## Explanation Requirement

For every analytical answer — variance, reconciliation, risk, prioritization, control
exceptions — the assistant must explain how the conclusion follows from the data it
retrieved.

An unexplained analytical answer is a failed answer, even when the number is correct.
Finance professionals must be able to verify reasoning, not just receive conclusions.

---

# Chapter 27 — Expansion Roadmap & Milestones

## Guiding Principle (Unchanged)

The application must always be demonstrable.

Every milestone ends with a running application, a passing test suite, and a passing
evaluation suite.

## Milestone 11 — Simulator v2 & Schema Foundation

Goal: the simulated company becomes a complete business.

Deliverables:

All new tables from Chapter 20 (Phases A, B, and C), migrated.
Structured company policies as data.
Configurable simulation date.
Extended seed generator producing all entities at the scale defined in Chapter 19.
All consistency invariants asserted by the check script.
All planted anomalies present and recorded in a machine-readable expectations file.
Read-only repositories for every new entity.

No new tools. No AI changes. The assistant continues to work exactly as before.

This milestone is deliberately AI-free. It de-risks everything that follows.

## Milestone 12 — Phase A Domains

Goal: Expense Management, Credit Management, Cash Flow Forecasting.

Deliverables:

Services and tools for all three domains.
Deterministic date-range resolution tool.
Tool descriptions with explicit disambiguation clauses.
Planner prompt updated and version-bumped.
Baseline tool-selection accuracy recorded before the change, and re-measured after.
At least thirty new evaluation cases.

Acceptance: all three domains answer accurately in the UI, and no previously passing
evaluation case regresses.

## Milestone 13 — Phase B Domains

Goal: Budgets and FP&A, Bank Reconciliation, Fixed Assets.

Deliverables:

Services and tools for all three domains.
Actuals always computed, never stored.
Depreciation always computed from the simulation date.
Deterministic reconciliation matching algorithm.
At least thirty new evaluation cases.
Tool-selection accuracy measured against the Milestone 12 baseline.

Acceptance: variance analysis explains causes, reconciliation identifies the seeded
unmatched transactions exactly, and asset book values are correct.

## Milestone 14 — Tool Selection at Scale

Goal: keep planning accurate as the tool set approaches fifty.

Deliverables:

Domain router implemented behind a configuration flag.
Structured planning output with schema validation and bounded retry.
Accuracy measured with routing on and routing off.
Routing enabled only if it demonstrably improves accuracy or latency.
Disambiguation clauses reviewed across every tool description.

Acceptance: full-suite tool-selection accuracy meets or exceeds the pre-expansion
baseline.

## Milestone 15 — Phase C Domains

Goal: Payroll Analysis, Procurement, Financial Close, Tax, Audit Support.

Deliverables:

Services and tools for all five domains.
Sensitive-domain response constraints enforced in the Phase 2 prompt.
Registry-level read-only assertion enforced at startup.
Refusal behavior for write requests, with evaluation cases proving it.
At least fifty new evaluation cases, including one hallucination trap per domain.

Acceptance: all eleven domains answer accurately, control questions return the exact
planted anomalies, and every write request is correctly refused and explained.

## Milestone 16 — Expansion Complete

Goal: audit, harden, document.

Deliverables:

Full evaluation suite green, with a per-domain scorecard.
Architecture audit: no SQL outside repositories, no business rules in tools or
endpoints, no policies in prompts, no keyword matching anywhere.
Latency profile per phase, with indexes verified for every analytical query.
Documentation for all eleven domains.
ADRs for domain routing, computed-not-stored actuals, and read-only enforcement.
Demo script covering one question from each of the eleven domains.

Acceptance: a finance professional can ask a question from any domain and receive an
accurate, explained, verifiable answer on localhost.
