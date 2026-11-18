"""The ops center.

Six agents, one dispatcher. Agents never call each other. Every handoff is a
state change on a row in the work register. That is what makes them lego: any
agent can be replaced, a new one inserted, or two implementations run in
parallel on the same queue and compared.

Each agent's core is a pure function with a typed input and output. The job
entry point in ops/entrypoints is thin. If an agent later needs to be served
interactively, it gets a second thin entry point wrapping the same function in
MLflow ResponsesAgent, with nothing in the agent itself changing.

ops/ may import from core/. ops/ must never import from app/.
"""
