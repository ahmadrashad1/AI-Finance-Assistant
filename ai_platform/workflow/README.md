# Workflow Framework

A small internal SDK for defining workflows so every workflow (chat request,
evaluation run, simulator seed, report generation, ...) follows the same
lifecycle instead of ad hoc orchestration:

    Initialize -> Validate -> Execute -> Log -> Evaluate -> Complete

No workflow may skip logging or evaluation. Each step should be an
independent, testable unit with explicit inputs/outputs, so the same
framework can back Finance today and HR/Procurement/Sales later.
