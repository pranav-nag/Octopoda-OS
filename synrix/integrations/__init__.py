"""
Octopoda Framework Integrations
================================
Drop-in memory for every major AI agent framework.

Usage:
    # LangChain
    from synrix.integrations.langchain import OctopodaMemory
    memory = OctopodaMemory(agent_id="my_agent")
    chain = ConversationChain(memory=memory, llm=llm)

    # CrewAI
    from synrix.integrations.crewai import OctopodaCrewMemory
    crew = Crew(memory=OctopodaCrewMemory(agent_id="my_crew"))

    # OpenAI Agents SDK
    from synrix.integrations.openai_agents import octopoda_tools
    agent = Agent(tools=octopoda_tools("my_agent"))

    # AutoGen
    from synrix.integrations.autogen import OctopodaAutoGenMemory
"""

__all__ = []

# Lazy imports — only load what the user actually needs
def __getattr__(name):
    if name == "OctopodaMemory":
        from .langchain import OctopodaMemory
        return OctopodaMemory
    if name == "OctopodaChatHistory":
        from .langchain import OctopodaChatHistory
        return OctopodaChatHistory
    if name == "OctopodaCrewMemory":
        from .crewai import OctopodaCrewMemory
        return OctopodaCrewMemory
    if name == "octopoda_tools":
        from .openai_agents import octopoda_tools
        return octopoda_tools
    if name == "OctopodaAutoGenMemory":
        from .autogen import OctopodaAutoGenMemory
        return OctopodaAutoGenMemory
    raise AttributeError(f"module 'synrix.integrations' has no attribute {name!r}")
