"""Tests du client Llama App (aucun accès réseau)."""

from __future__ import annotations

import pytest

from trading_matrix.core import llama_client


def test_models_from_openai_payload() -> None:
    payload = {
        "data": [
            {"id": "ggml-org/gemma-4-e4b-it-GGUF:Q4_0"},
            {"id": "Qwen/Qwen3-8B-GGUF"},
            {"id": "ggml-org/gemma-4-e4b-it-GGUF:Q4_0"},
        ]
    }
    assert llama_client._models_from_payload(payload) == [
        "ggml-org/gemma-4-e4b-it-GGUF:Q4_0",
        "Qwen/Qwen3-8B-GGUF",
    ]


def test_stream_chunks_extract_content_and_reasoning() -> None:
    lines = iter(
        [
            ": ping",
            "",
            'data: {"choices":[{"delta":{"reasoning_content":"Je vérifie."}}]}',
            'data: {"choices":[{"delta":{"content":"Signal haussier"}}]}',
            "data: pas-du-json",
            "data: [DONE]",
            'data: {"choices":[{"delta":{"content":"ignoré"}}]}',
        ]
    )
    assert list(llama_client._stream_chunks(lines)) == [
        ("thinking", "Je vérifie."),
        ("content", "Signal haussier"),
    ]


def test_stream_error_is_reported() -> None:
    lines = iter(['data: {"error":{"message":"modèle indisponible"}}'])
    with pytest.raises(llama_client.LlamaError, match="modèle indisponible"):
        list(llama_client._stream_chunks(lines))


def test_base_url_accepts_v1_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLAMA_HOST", "http://127.0.0.1:9931/v1")
    assert llama_client.base_url() == "http://127.0.0.1:9931"
