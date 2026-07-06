from langgraph.graph import StateGraph, START, END
from kalam.agents.coder.schema.state import CoderState
from kalam.agents.coder.nodes.decomposer import decomposer_node
from kalam.agents.coder.nodes.context_retriever import context_retriever_node
from kalam.agents.coder.nodes.brain import brain_node
from kalam.agents.coder.nodes.verifier import verifier_node
from kalam.agents.coder.nodes.checkpoint import checkpoint_node

builder = StateGraph(CoderState)
builder.add_node("decomposer", decomposer_node)
builder.add_node("context_retriever", context_retriever_node)
builder.add_node("brain", brain_node)
builder.add_node("verifier", verifier_node)
builder.add_node("checkpoint", checkpoint_node)

builder.add_edge(START, "decomposer")
builder.add_edge("decomposer", "context_retriever")
builder.add_edge("context_retriever", "brain")
builder.add_edge("brain", "verifier")
builder.add_edge("verifier", "checkpoint")
builder.add_edge("checkpoint", END)

coder_graph = builder.compile()
