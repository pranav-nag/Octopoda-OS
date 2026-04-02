"""
Tests for framework integrations — LangChain, CrewAI, AutoGen, OpenAI Agents.

All tests use the SQLite backend (injected via backend= param) to verify
data actually persists, NOT the in-memory mock.
"""

import os
import pytest


class TestLangChainIntegration:

    def test_default_backend_is_not_mock(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)
        from synrix_runtime.integrations.langchain_memory import SynrixMemory
        mem = SynrixMemory(agent_id="lc_test")
        assert mem.backend.backend_type != "mock"

    def test_save_and_load_context(self, agent_backend):
        from synrix_runtime.integrations.langchain_memory import SynrixMemory
        mem = SynrixMemory(agent_id="lc_test", backend=agent_backend)

        mem.save_context({"input": "Hello"}, {"output": "Hi there!"})
        mem.save_context({"input": "How are you?"}, {"output": "I'm good!"})

        variables = mem.load_memory_variables({})
        history = variables["history"]
        assert "Hello" in history
        assert "Hi there!" in history

    def test_get_full_history(self, agent_backend):
        from synrix_runtime.integrations.langchain_memory import SynrixMemory
        mem = SynrixMemory(agent_id="lc_hist", backend=agent_backend)

        mem.save_context({"input": "A"}, {"output": "B"})
        mem.save_context({"input": "C"}, {"output": "D"})

        history = mem.get_full_history()
        assert len(history) == 2

    def test_restore_from_crash(self, agent_backend):
        from synrix_runtime.integrations.langchain_memory import SynrixMemory
        mem1 = SynrixMemory(agent_id="lc_crash", backend=agent_backend)
        mem1.save_context({"input": "X"}, {"output": "Y"})
        mem1.save_context({"input": "W"}, {"output": "Z"})

        # Simulate crash: new instance, same backend
        mem2 = SynrixMemory(agent_id="lc_crash", backend=agent_backend)
        count = mem2.restore_from_crash()
        assert count == 2

    def test_entity_storage(self, agent_backend):
        from synrix_runtime.integrations.langchain_memory import SynrixMemory
        mem = SynrixMemory(agent_id="lc_entity", backend=agent_backend)

        mem.store_entity("John", {"role": "CEO", "company": "Acme"})
        entity = mem.get_entity("John")
        assert entity is not None
        assert entity.get("role") == "CEO"


class TestCrewAIIntegration:

    def test_default_backend_is_not_mock(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)
        from synrix_runtime.integrations.crewai_memory import SynrixCrewMemory
        mem = SynrixCrewMemory(crew_id="crew_test")
        assert mem.backend.backend_type != "mock"

    def test_store_and_get_finding(self, agent_backend):
        from synrix_runtime.integrations.crewai_memory import SynrixCrewMemory
        mem = SynrixCrewMemory(crew_id="crew_1", backend=agent_backend)

        mem.store_finding("researcher", "market_size", {"value": "$4.2B"})
        finding = mem.get_finding("market_size")
        assert finding is not None
        assert finding.get("value") == "$4.2B"

    def test_crew_snapshot_and_restore(self, agent_backend):
        from synrix_runtime.integrations.crewai_memory import SynrixCrewMemory
        mem = SynrixCrewMemory(crew_id="crew_snap", backend=agent_backend)

        mem.store_finding("analyst", "growth_rate", {"value": "15%"})
        snap = mem.crew_snapshot("test_snap")
        assert snap["items"] >= 1

        result = mem.crew_restore("test_snap")
        assert result["restored"]


class TestAutoGenIntegration:

    def test_default_backend_is_not_mock(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)
        from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory
        mem = SynrixAutoGenMemory(group_id="ag_test")
        assert mem.backend.backend_type != "mock"

    def test_store_and_retrieve_messages(self, agent_backend):
        from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory
        mem = SynrixAutoGenMemory(group_id="ag_1", backend=agent_backend)

        mem.store_message("alice", "bob", "Hello Bob")
        mem.store_message("bob", "alice", "Hi Alice")

        history = mem.get_conversation_history()
        assert len(history) == 2

    def test_search_conversations(self, agent_backend):
        from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory
        mem = SynrixAutoGenMemory(group_id="ag_search", backend=agent_backend)

        mem.store_message("alice", "bob", "The quarterly revenue is $10M")
        mem.store_message("bob", "alice", "Thanks for the update")

        matches = mem.search_conversations("revenue")
        assert len(matches) == 1

    def test_get_stats(self, agent_backend):
        from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory
        mem = SynrixAutoGenMemory(group_id="ag_stats", backend=agent_backend)

        mem.store_message("a1", "a2", "msg1")
        mem.store_message("a2", "a1", "msg2")

        stats = mem.get_stats()
        assert stats["total_messages"] == 2
        assert stats["unique_agents"] == 2


class TestOpenAIAgentsIntegration:

    def test_default_backend_is_not_mock(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)
        from synrix_runtime.integrations.openai_agents import SynrixOpenAIMemory
        mem = SynrixOpenAIMemory()
        assert mem.backend.backend_type != "mock"

    def test_store_and_restore_thread(self, agent_backend):
        from synrix_runtime.integrations.openai_agents import SynrixOpenAIMemory
        mem = SynrixOpenAIMemory(backend=agent_backend)

        mem.store_thread_state("thread_123", {"messages": [{"role": "user", "content": "Hi"}]})
        result = mem.restore_thread("thread_123")
        assert result["found"]
        assert "messages" in result["state"]

    def test_store_run_result(self, agent_backend):
        from synrix_runtime.integrations.openai_agents import SynrixOpenAIMemory
        mem = SynrixOpenAIMemory(backend=agent_backend)

        mem.store_run_result("run_abc", {"output": "Analysis complete", "agent_name": "analyst"})
        runs = mem.get_all_runs()
        assert len(runs) >= 1

    def test_get_agent_history(self, agent_backend):
        from synrix_runtime.integrations.openai_agents import SynrixOpenAIMemory
        mem = SynrixOpenAIMemory(backend=agent_backend)

        mem.store_run_result("run_1", {"agent_name": "writer", "output": "Draft"})
        mem.store_run_result("run_2", {"agent_name": "editor", "output": "Edited"})
        mem.store_run_result("run_3", {"agent_name": "writer", "output": "Final"})

        writer_history = mem.get_agent_history("writer")
        assert len(writer_history) == 2


# =========================================================================
# v2 Integration Tests — synrix.integrations.* (new Octopoda integrations)
# =========================================================================

class TestV2CrewAIIntegration:
    """Test the new CrewAI integration (synrix.integrations.crewai)."""

    def test_import(self):
        from synrix.integrations.crewai import OctopodaCrewMemory
        assert OctopodaCrewMemory is not None

    def test_basic_remember_recall(self):
        from synrix.integrations.crewai import OctopodaCrewMemory
        mem = OctopodaCrewMemory(agent_id="test_v2_crew_basic")
        assert mem.remember("project", "Quantum Computing Research") is True
        val = mem.recall("project")
        assert val is not None
        assert "Quantum" in str(val)

    def test_crew_results(self):
        from synrix.integrations.crewai import OctopodaCrewMemory
        mem = OctopodaCrewMemory(agent_id="test_v2_crew_results", crew_name="research_crew")
        mem.save_crew_result("analysis", "Found 5 key breakthroughs")
        result = mem.get_crew_result("analysis")
        assert result is not None
        assert "breakthroughs" in str(result)

    def test_agent_output(self):
        from synrix.integrations.crewai import OctopodaCrewMemory
        mem = OctopodaCrewMemory(agent_id="test_v2_crew_agent_out", crew_name="my_crew")
        mem.save_agent_output("researcher", "data_collection", "Collected 100 papers")
        outputs = mem.get_agent_outputs("researcher")
        assert len(outputs) > 0

    def test_shared_knowledge(self):
        from synrix.integrations.crewai import OctopodaCrewMemory
        mem = OctopodaCrewMemory(agent_id="test_v2_crew_shared", crew_name="shared_crew")
        mem.save_shared_knowledge("api_endpoint", "https://api.example.com")
        val = mem.get_shared_knowledge("api_endpoint")
        assert val is not None

    def test_crew_summary(self):
        from synrix.integrations.crewai import OctopodaCrewMemory
        mem = OctopodaCrewMemory(agent_id="test_v2_crew_summary", crew_name="summary_crew")
        mem.save_crew_result("task1", "Result 1")
        mem.save_agent_output("agent1", "task1", "Output 1")
        mem.save_shared_knowledge("key1", "Value 1")
        summary = mem.get_crew_summary()
        assert summary["crew_name"] == "summary_crew"
        assert summary["total_memories"] > 0

    def test_callbacks(self):
        from synrix.integrations.crewai import OctopodaCrewMemory
        mem = OctopodaCrewMemory(agent_id="test_v2_crew_cb", crew_name="callback_crew")
        mem.on_task_start("research", "researcher")
        mem.on_task_complete("research", "researcher", "Found 10 papers")
        mem.on_crew_complete("Final report: 10 papers analyzed")
        result = mem.get_crew_result("research")
        assert result is not None


class TestV2OpenAIAgentsIntegration:
    """Test the new OpenAI Agents SDK integration (synrix.integrations.openai_agents)."""

    def test_import(self):
        from synrix.integrations.openai_agents import octopoda_tools, handle_tool_call
        assert octopoda_tools is not None
        assert handle_tool_call is not None

    def test_remember_and_recall(self):
        import json
        from synrix.integrations.openai_agents import remember, recall
        result = json.loads(remember("test_v2_oai_basic", "user_name", "Alice"))
        assert result["stored"] is True
        result = json.loads(recall("test_v2_oai_basic", "user_name"))
        assert result["found"] is True
        assert "Alice" in str(result["value"])

    def test_handle_tool_call(self):
        import json
        from synrix.integrations.openai_agents import handle_tool_call
        result = json.loads(handle_tool_call(
            "test_v2_oai_handler", "remember_memory",
            {"key": "color", "value": "blue"},
        ))
        assert result["stored"] is True
        result = json.loads(handle_tool_call(
            "test_v2_oai_handler", "recall_memory",
            {"key": "color"},
        ))
        assert result["found"] is True

    def test_plain_tool_definitions(self):
        from synrix.integrations.openai_agents import _plain_tool_definitions
        tools = _plain_tool_definitions("test_agent")
        assert len(tools) == 5
        names = [t["function"]["name"] for t in tools]
        assert "remember_memory" in names
        assert "recall_memory" in names
        assert "search_memories" in names

    def test_octopoda_tools_fallback(self):
        from synrix.integrations.openai_agents import octopoda_tools
        tools = octopoda_tools("test_v2_fallback")
        assert len(tools) >= 5


class TestV2AutoGenIntegration:
    """Test the new AutoGen integration (synrix.integrations.autogen)."""

    def test_import(self):
        from synrix.integrations.autogen import OctopodaAutoGenMemory
        assert OctopodaAutoGenMemory is not None

    def test_basic_remember_recall(self):
        from synrix.integrations.autogen import OctopodaAutoGenMemory
        mem = OctopodaAutoGenMemory(agent_id="test_v2_ag_basic")
        assert mem.remember("name", "Bob") is True
        val = mem.recall("name")
        assert val is not None
        assert "Bob" in str(val)

    def test_learn_from_conversation(self):
        from synrix.integrations.autogen import OctopodaAutoGenMemory
        mem = OctopodaAutoGenMemory(agent_id="test_v2_ag_learn")
        messages = [
            {"role": "user", "content": "My name is Charlie"},
            {"role": "assistant", "content": "Nice to meet you, Charlie!"},
            {"role": "user", "content": "I need help with our Q4 report"},
        ]
        stored = mem.learn_from_conversation(messages)
        assert stored >= 3

    def test_get_relevant_context(self):
        from synrix.integrations.autogen import OctopodaAutoGenMemory
        mem = OctopodaAutoGenMemory(agent_id="test_v2_ag_context")
        mem.remember("tech_stack", "Python, FastAPI, React")
        context = mem.get_relevant_context("what technologies")
        assert isinstance(context, str)

    def test_group_chat(self):
        from synrix.integrations.autogen import OctopodaAutoGenMemory
        mem = OctopodaAutoGenMemory(agent_id="test_v2_ag_group")
        mem.save_group_message("researcher", "Found papers", "research_group")
        mem.save_group_message("analyst", "3 are cited", "research_group")
        history = mem.get_group_history("research_group")
        assert len(history) >= 2


class TestV2LangChainIntegrationBasic:
    """Test LangChain v2 integration can be imported."""

    def test_import(self):
        from synrix.integrations.langchain import OctopodaMemory, OctopodaChatHistory
        assert OctopodaMemory is not None
        assert OctopodaChatHistory is not None


class TestV2IntegrationsModule:
    """Test the integrations module lazy imports."""

    def test_lazy_import_crewai(self):
        from synrix.integrations import OctopodaCrewMemory
        assert OctopodaCrewMemory is not None

    def test_lazy_import_openai(self):
        from synrix.integrations import octopoda_tools
        assert octopoda_tools is not None

    def test_lazy_import_autogen(self):
        from synrix.integrations import OctopodaAutoGenMemory
        assert OctopodaAutoGenMemory is not None

    def test_invalid_import(self):
        with pytest.raises(AttributeError):
            from synrix import integrations
            integrations.NonExistentThing
