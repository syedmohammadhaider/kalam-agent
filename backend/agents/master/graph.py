from langgraph.graph import StateGraph, START, END
from agents.master.schema.state import MasterState
from agents.master.nodes.planner import planner_node
from agents.master.nodes.designer import designer_node, needs_design
from agents.master.nodes.executor import executor_node
from agents.master.nodes.shell_executor import shell_executor_node

builder = StateGraph(MasterState)
builder.add_node("planner", planner_node)
builder.add_node("designer", designer_node)
builder.add_node("executor", executor_node)
builder.add_node("shell_executor", shell_executor_node)

builder.add_edge(START, "planner")
builder.add_conditional_edges(
    "planner",
    needs_design,
    {True: "designer", False: "executor"},
)
builder.add_edge("designer", "executor")
builder.add_edge("executor", "shell_executor")
builder.add_edge("shell_executor", END)

master_graph = builder.compile()
