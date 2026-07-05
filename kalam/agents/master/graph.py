from langgraph.graph import StateGraph, START, END
from kalam.agents.master.schema.state import MasterState
from kalam.agents.master.nodes.planner import planner_node
from kalam.agents.master.nodes.designer import designer_node, needs_design
from kalam.agents.master.nodes.executor import executor_node

builder = StateGraph(MasterState)
builder.add_node("planner", planner_node)
builder.add_node("designer", designer_node)
builder.add_node("executor", executor_node)

builder.add_edge(START, "planner")
builder.add_conditional_edges(
    "planner",
    needs_design,
    {True: "designer", False: "executor"},
)
builder.add_edge("designer", "executor")
builder.add_edge("executor", END)

master_graph = builder.compile()
