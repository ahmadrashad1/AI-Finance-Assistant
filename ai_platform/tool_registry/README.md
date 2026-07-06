# Tool Registry

Central registration point for every deterministic tool exposed to the LLM
planner. The planner reads only this registry — never the codebase, never
raw Python functions.

Each registered tool declares: name, description, required/optional
parameters, return schema, version, and owning domain. See
`docs/adr/0004-tool-registry.md` for why this exists instead of automatic
function discovery.
