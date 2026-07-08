"""Deterministic tests for the OpenAI transport translation layer and the
native /rerank response parsing. No network: native_rerank is driven through
a mocked httpx transport.
"""
from __future__ import annotations

import json

import httpx
import pytest


# --------------------------------------------------------------------------
# to_openai_tools: input_schema -> function.parameters
# --------------------------------------------------------------------------
def test_to_openai_tools_maps_input_schema():
    from core.openai_transport import to_openai_tools

    schema = {"type": "object", "properties": {"q": {"type": "string"}}}
    out = to_openai_tools(
        [{"name": "search", "description": "d", "input_schema": schema}]
    )
    assert out == [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "d",
                "parameters": schema,
            },
        }
    ]
    assert to_openai_tools(None) is None
    assert to_openai_tools([]) is None


def test_to_openai_tools_default_parameters():
    from core.openai_transport import to_openai_tools

    out = to_openai_tools([{"name": "noargs"}])
    assert out[0]["function"]["parameters"] == {
        "type": "object", "properties": {}
    }


# --------------------------------------------------------------------------
# to_openai_messages: system prefix, str passthrough, tool_use, tool_result
# --------------------------------------------------------------------------
def test_to_openai_messages_system_and_string():
    from core.openai_transport import to_openai_messages

    out = to_openai_messages("SYS", [{"role": "user", "content": "hi"}])
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[1] == {"role": "user", "content": "hi"}


def test_to_openai_messages_no_system_when_blank():
    from core.openai_transport import to_openai_messages

    out = to_openai_messages("   ", [{"role": "user", "content": "hi"}])
    assert out == [{"role": "user", "content": "hi"}]


def test_to_openai_messages_assistant_tool_use():
    from core.openai_transport import to_openai_messages

    msg = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "let me check"},
            {"type": "tool_use", "id": "call_1", "name": "lookup",
             "input": {"x": 1}},
        ],
    }
    out = to_openai_messages("", [msg])
    assert out[0]["role"] == "assistant"
    assert out[0]["content"] == "let me check"
    tc = out[0]["tool_calls"][0]
    assert tc["id"] == "call_1"
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "lookup"
    assert json.loads(tc["function"]["arguments"]) == {"x": 1}


def test_to_openai_messages_tool_result_becomes_tool_message():
    from core.openai_transport import to_openai_messages

    msg = {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call_1",
             "content": "the answer"},
        ],
    }
    out = to_openai_messages("", [msg])
    assert out == [
        {"role": "tool", "tool_call_id": "call_1", "content": "the answer"}
    ]


def test_to_openai_messages_tool_result_serializes_nonstring():
    from core.openai_transport import to_openai_messages

    msg = {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "c", "content": {"a": 1}},
        ],
    }
    out = to_openai_messages("", [msg])
    assert json.loads(out[0]["content"]) == {"a": 1}


# --------------------------------------------------------------------------
# openai_message_to_blocks: non-streamed response -> content blocks
# --------------------------------------------------------------------------
def test_openai_message_to_blocks_text_and_tool():
    from core.openai_transport import openai_message_to_blocks

    message = {
        "content": "hello",
        "tool_calls": [
            {"id": "c1", "function": {"name": "f", "arguments": '{"a": 2}'}},
        ],
    }
    blocks = openai_message_to_blocks(message)
    assert blocks[0] == {"type": "text", "text": "hello"}
    assert blocks[1] == {
        "type": "tool_use", "id": "c1", "name": "f", "input": {"a": 2}
    }


def test_openai_message_to_blocks_bad_arguments_default_empty():
    from core.openai_transport import openai_message_to_blocks

    message = {"content": None, "tool_calls": [
        {"id": "c1", "function": {"name": "f", "arguments": "not-json"}},
    ]}
    blocks = openai_message_to_blocks(message)
    assert blocks == [
        {"type": "tool_use", "id": "c1", "name": "f", "input": {}}
    ]


# --------------------------------------------------------------------------
# OpenAIStreamAccumulator: streamed deltas -> ordered blocks + stop reason
# --------------------------------------------------------------------------
def test_stream_accumulator_text_then_tool():
    from core.openai_transport import OpenAIStreamAccumulator

    acc = OpenAIStreamAccumulator()
    assert acc.add_delta({"content": "Hel"}) == "Hel"
    assert acc.add_delta({"content": "lo"}) == "lo"
    # tool call arrives split across deltas
    acc.add_delta({"tool_calls": [
        {"index": 0, "id": "c1", "function": {"name": "search",
         "arguments": '{"q":'}}]})
    acc.add_delta({"tool_calls": [
        {"index": 0, "function": {"arguments": '"hi"}'}}]},
        finish_reason="tool_calls")
    blocks, stop = acc.finalize()
    assert blocks[0] == {"type": "text", "text": "Hello"}
    assert blocks[1] == {
        "type": "tool_use", "id": "c1", "name": "search",
        "input": {"q": "hi"},
    }
    assert stop == "tool_use"


def test_stream_accumulator_stop_maps_to_end_turn():
    from core.openai_transport import OpenAIStreamAccumulator

    acc = OpenAIStreamAccumulator()
    acc.add_delta({"content": "done"}, finish_reason="stop")
    blocks, stop = acc.finalize()
    assert blocks == [{"type": "text", "text": "done"}]
    assert stop == "end_turn"


# --------------------------------------------------------------------------
# native_rerank: parses gateway /rerank response, maps index -> candidate id
# --------------------------------------------------------------------------
def _mock_rerank(handler):
    """Patch httpx.Client.post to call `handler(request_json)` -> response."""
    import kb.reranker as rr

    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):
            return _Resp(handler(json))

    return _Client


def test_native_rerank_maps_index_and_sorts(monkeypatch):
    import kb.reranker as rr

    candidates = [("id-a", "alpha"), ("id-b", "bravo"), ("id-c", "charlie")]

    def handler(body):
        # gateway returns results out of order, by index, with scores
        assert body["model"] == "azure.cohere-rerank-v3-english"
        assert body["top_n"] == 2
        return {"results": [
            {"index": 2, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.5},
        ]}

    monkeypatch.setattr(rr.httpx, "Client", _mock_rerank(handler))
    out = rr.native_rerank(
        base_url="https://gw", api_key="k",
        model="azure.cohere-rerank-v3-english",
        query="q", candidates=candidates, top_k=2,
    )
    assert out == [("id-c", 0.9), ("id-a", 0.5)]


def test_native_rerank_none_without_key():
    import kb.reranker as rr

    assert rr.native_rerank(
        base_url="https://gw", api_key="", model="m",
        query="q", candidates=[("a", "x")], top_k=1,
    ) is None


def test_native_rerank_none_on_empty_results(monkeypatch):
    import kb.reranker as rr

    monkeypatch.setattr(
        rr.httpx, "Client", _mock_rerank(lambda body: {"results": []})
    )
    out = rr.native_rerank(
        base_url="https://gw", api_key="k", model="m",
        query="q", candidates=[("a", "x")], top_k=1,
    )
    assert out is None


# --------------------------------------------------------------------------
# llm_rerank: fake client returning a JSON index array -> ordered ids
# --------------------------------------------------------------------------
def test_llm_rerank_orders_ids():
    import kb.reranker as rr

    class _Out:
        text = "[2, 0]"

    class _Client:
        async def complete_async(self, **kwargs):
            return _Out()

    candidates = [("id-a", "alpha"), ("id-b", "bravo"), ("id-c", "charlie")]
    ids = rr.llm_rerank(_Client(), "model", "q", candidates, top_k=2)
    assert ids == ["id-c", "id-a"]


def test_llm_rerank_none_without_client():
    import kb.reranker as rr

    assert rr.llm_rerank(None, "m", "q", [("a", "x")], 1) is None
