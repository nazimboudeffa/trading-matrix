"""Client minimal pour l'API locale compatible OpenAI de Llama App.

Llama App (llama.cpp) expose un serveur sur ``http://127.0.0.1:9931`` avec des
endpoints ``/v1/...``. Ce module ne dépend pas de Qt : il est utilisable hors
interface pour tester l'installation.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import requests

DEFAULT_HOST = "http://127.0.0.1:9931"


class LlamaError(RuntimeError):
    """Erreur de communication avec Llama App."""


def base_url() -> str:
    """URL du serveur Llama (surchargeable via ``LLAMA_HOST``)."""
    raw = (os.environ.get("LLAMA_HOST") or DEFAULT_HOST).strip()
    if not raw:
        raw = DEFAULT_HOST
    if not raw.startswith(("http://", "https://")):
        raw = "http://" + raw
    raw = raw.rstrip("/")
    if raw.endswith("/v1"):
        raw = raw[:-3]
    return raw


def _auth_headers() -> dict[str, str]:
    """Ajoute le bearer token si le serveur a été lancé avec ``--api-key``."""
    key = (os.environ.get("LLAMA_API_KEY") or "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def find_executable() -> str | None:
    """Cherche le binaire ``llama`` (PATH puis emplacements connus)."""
    exe = shutil.which("llama") or shutil.which("llama-server")
    if exe:
        return exe

    candidates: list[Path] = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.extend(
            [
                Path(local_appdata) / "Programs" / "Llama" / "llama.exe",
                Path(local_appdata) / "Programs" / "llama.cpp" / "llama.exe",
                Path(local_appdata) / "Programs" / "llama.cpp" / "llama-server.exe",
            ]
        )
    program_files = os.environ.get("ProgramFiles") or os.environ.get("ProgramFiles(x86)")
    if program_files:
        candidates.extend(
            [
                Path(program_files) / "Llama" / "llama.exe",
                Path(program_files) / "llama.cpp" / "llama-server.exe",
            ]
        )
    candidates.extend(
        [
            Path("/usr/local/bin/llama"),
            Path("/usr/bin/llama"),
            Path("/opt/homebrew/bin/llama"),
            Path("/Applications/Llama.app/Contents/Resources/llama"),
            Path.home() / ".local" / "bin" / "llama",
        ]
    )
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


@dataclass
class LlamaStatus:
    """État d'installation / d'exécution de Llama App."""

    installed: bool
    running: bool
    models: list[str] = field(default_factory=list)
    error: str = ""
    executable: str | None = None

    @property
    def ready(self) -> bool:
        """Vrai si un modèle est utilisable immédiatement."""
        return self.running and bool(self.models)


def _error_text(error: object) -> str:
    """Extrait le message d'une erreur au format OpenAI ou llama.cpp."""
    if isinstance(error, dict):
        return str(error.get("message") or error.get("error") or "")
    return str(error or "")


def _error_from_response(response: requests.Response) -> str:
    message = ""
    try:
        payload = response.json()
    except ValueError:
        message = (response.text or "").strip()
    else:
        if isinstance(payload, dict):
            message = _error_text(payload.get("error"))
            if not message:
                message = str(payload.get("message") or payload.get("detail") or "")
    prefix = f"Erreur Llama ({response.status_code})"
    return f"{prefix} : {message}" if message else prefix


def _models_from_payload(payload: dict) -> list[str]:
    """Lit ``GET /v1/models`` (avec repli sur la liste native ``models``)."""
    models = payload.get("data")
    if not isinstance(models, list):
        models = payload.get("models")
    if not isinstance(models, list):
        return []

    names: list[str] = []
    seen: set[str] = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("id") or item.get("name") or item.get("model")
        if name and str(name) not in seen:
            seen.add(str(name))
            names.append(str(name))
    return names


def _get_json(path: str, timeout: float) -> dict:
    try:
        response = requests.get(
            base_url() + path, headers=_auth_headers(), timeout=timeout
        )
    except requests.RequestException as exc:
        raise LlamaError(f"Serveur Llama injoignable ({base_url()}) : {exc}") from exc
    if response.status_code >= 400:
        raise LlamaError(_error_from_response(response))
    try:
        payload = response.json()
    except ValueError as exc:
        raise LlamaError("Réponse invalide du serveur Llama.") from exc
    if not isinstance(payload, dict):
        raise LlamaError("Réponse inattendue du serveur Llama.")
    return payload


def fetch_models(timeout: float = 4.0) -> list[str]:
    """Liste les modèles disponibles sur le serveur Llama."""
    return _models_from_payload(_get_json("/v1/models", timeout=timeout))


def get_status(timeout: float = 2.5) -> LlamaStatus:
    """Vérifie si Llama App est installé, démarré, et quels modèles existent."""
    executable = find_executable()
    try:
        payload = _get_json("/v1/models", timeout=timeout)
    except LlamaError as exc:
        return LlamaStatus(
            installed=bool(executable),
            running=False,
            error=str(exc),
            executable=executable,
        )
    return LlamaStatus(
        installed=True,
        running=True,
        models=_models_from_payload(payload),
        executable=executable,
    )


def _stream_chunks(
    lines: Iterator[str], stop_event: threading.Event | None = None
) -> Iterator[tuple[str, str]]:
    """Décode les lignes SSE de ``/v1/chat/completions`` en ``(kind, texte)``."""
    for raw in lines:
        if stop_event is not None and stop_event.is_set():
            return
        if not raw:
            continue
        line = raw.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data:
            continue
        if data == "[DONE]":
            return
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("error"):
            raise LlamaError(
                _error_text(event["error"]) or "Erreur du serveur Llama."
            )

        choices = event.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            thinking = (
                delta.get("reasoning_content")
                or delta.get("reasoning")
                or delta.get("thinking")
            )
            content = delta.get("content")
            if thinking:
                yield "thinking", str(thinking)
            if content:
                yield "content", str(content)


def chat_stream(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    timeout: tuple[float, float | None] = (5.0, 600.0),
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[str, str]]:
    """Envoie une conversation et diffuse la réponse du modèle.

    Yields des tuples ``(type, texte)`` où ``type`` vaut ``"content"`` ou
    ``"thinking"`` (raisonnement exposé par les modèles compatibles). Lève
    ``LlamaError`` en cas de problème réseau ou de réponse en erreur.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": float(temperature),
    }

    try:
        response = requests.post(
            base_url() + "/v1/chat/completions",
            json=payload,
            headers=_auth_headers(),
            stream=True,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise LlamaError(
            f"Impossible de contacter Llama App ({base_url()}) : {exc}"
        ) from exc

    with response:
        if response.status_code >= 400:
            raise LlamaError(_error_from_response(response))
        try:
            yield from _stream_chunks(
                response.iter_lines(decode_unicode=True), stop_event
            )
        except requests.RequestException as exc:
            raise LlamaError(f"Flux Llama interrompu : {exc}") from exc
