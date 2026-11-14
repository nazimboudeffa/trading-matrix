"""Client minimal pour l'API locale d'Ollama.

Ollama est un serveur local (par défaut ``http://127.0.0.1:11434``) qui expose
les modèles installés sur la machine. Ce module ne dépend pas de Qt : il est
utilisable hors interface pour tester l'installation.
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

DEFAULT_HOST = "http://127.0.0.1:11434"


class OllamaError(RuntimeError):
    """Erreur de communication avec Ollama."""


def base_url() -> str:
    """URL du serveur Ollama (surchargeable via ``OLLAMA_HOST``)."""
    raw = (os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).strip()
    if not raw:
        raw = DEFAULT_HOST
    if not raw.startswith(("http://", "https://")):
        raw = "http://" + raw
    return raw.rstrip("/")


def find_executable() -> str | None:
    """Cherche le binaire ``ollama`` (PATH puis emplacements connus)."""
    exe = shutil.which("ollama")
    if exe:
        return exe

    candidates: list[Path] = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe")
    candidates.extend(
        [
            Path("/usr/local/bin/ollama"),
            Path("/usr/bin/ollama"),
            Path("/opt/homebrew/bin/ollama"),
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            Path.home() / ".local" / "bin" / "ollama",
        ]
    )
    for path in candidates:
        if path.exists():
            return str(path)
    return None


@dataclass
class OllamaStatus:
    """État d'installation / d'exécution d'Ollama."""

    installed: bool
    running: bool
    models: list[str] = field(default_factory=list)
    error: str = ""
    executable: str | None = None

    @property
    def ready(self) -> bool:
        """Vrai si un modèle est utilisable immédiatement."""
        return self.running and bool(self.models)


def _error_from_response(response: requests.Response) -> str:
    message = ""
    try:
        payload = response.json()
        message = str(payload.get("error") or payload.get("message") or "")
    except ValueError:
        message = (response.text or "").strip()
    prefix = f"Erreur Ollama ({response.status_code})"
    return f"{prefix} : {message}" if message else prefix


def _models_from_payload(payload: dict) -> list[str]:
    models: list[str] = []
    seen: set[str] = set()
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name and str(name) not in seen:
            seen.add(str(name))
            models.append(str(name))
    return models


def _get_json(path: str, timeout: float) -> dict:
    try:
        response = requests.get(base_url() + path, timeout=timeout)
    except requests.RequestException as exc:
        raise OllamaError(f"Serveur Ollama injoignable ({base_url()}) : {exc}") from exc
    if response.status_code >= 400:
        raise OllamaError(_error_from_response(response))
    try:
        payload = response.json()
    except ValueError as exc:
        raise OllamaError("Réponse invalide du serveur Ollama.") from exc
    if not isinstance(payload, dict):
        raise OllamaError("Réponse inattendue du serveur Ollama.")
    return payload


def fetch_models(timeout: float = 4.0) -> list[str]:
    """Liste les modèles disponibles sur le serveur Ollama."""
    return _models_from_payload(_get_json("/api/tags", timeout=timeout))


def get_status(timeout: float = 2.5) -> OllamaStatus:
    """Vérifie si Ollama est installé, démarré, et quels modèles existent."""
    executable = find_executable()
    try:
        payload = _get_json("/api/tags", timeout=timeout)
    except OllamaError as exc:
        return OllamaStatus(
            installed=bool(executable),
            running=False,
            error=str(exc),
            executable=executable,
        )
    return OllamaStatus(
        installed=True,
        running=True,
        models=_models_from_payload(payload),
        executable=executable,
    )


def chat_stream(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    num_ctx: int = 8192,
    timeout: tuple[float, float | None] = (5.0, 600.0),
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[str, str]]:
    """Envoie une conversation et diffuse la réponse du modèle.

    Yields des tuples ``(type, texte)`` où ``type`` vaut ``"content"`` ou
    ``"thinking"`` (raisonnement de certains modèles). Lève ``OllamaError`` en
    cas de problème réseau ou de réponse en erreur.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": float(temperature),
            "num_ctx": int(num_ctx),
        },
    }

    try:
        response = requests.post(
            base_url() + "/api/chat",
            json=payload,
            stream=True,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise OllamaError(
            f"Impossible de contacter Ollama ({base_url()}) : {exc}"
        ) from exc

    with response:
        if response.status_code >= 400:
            raise OllamaError(_error_from_response(response))

        try:
            for raw in response.iter_lines(decode_unicode=True):
                if stop_event is not None and stop_event.is_set():
                    return
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("error"):
                    raise OllamaError(str(event["error"]))

                message = event.get("message") or {}
                thinking = message.get("thinking")
                content = message.get("content")
                if thinking:
                    yield "thinking", str(thinking)
                if content:
                    yield "content", str(content)
                if event.get("done"):
                    return
        except requests.RequestException as exc:
            raise OllamaError(f"Flux Ollama interrompu : {exc}") from exc
