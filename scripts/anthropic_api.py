"""Acesso à API de mensagens da Anthropic e medição da resposta em streaming."""

import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable, Iterator, Mapping, TypedDict
from urllib.request import Request, urlopen


API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
TIMEOUT_SECONDS = 120


class EventKind(StrEnum):
    ERROR = "error"
    MESSAGE_START = "message_start"
    CONTENT_DELTA = "content_block_delta"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_STOP = "message_stop"


class DeltaKind(StrEnum):
    TEXT = "text_delta"


class MessageResult(TypedDict):
    status: int
    model: str
    ttft_s: float | None
    latency_s: float
    stop_reason: str | None
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    input_tokens_total: int
    output_tokens: int


def _messages(prompt: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": prompt}]


def _request(api_key: str, path: str, body: Mapping[str, object]) -> Request:
    return Request(
        API_URL + path,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )


def count_input_tokens(api_key: str, model: str, prompt: str) -> int:
    body = {"model": model, "messages": _messages(prompt)}
    with urlopen(_request(api_key, "/count_tokens", body), timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)["input_tokens"]


def _stream_events(response: Iterable[bytes]) -> Iterator[tuple[dict[str, Any], float]]:
    """Lê eventos SSE e registra quando a última linha de dados chegou."""
    data_lines: list[str] = []
    data_time = 0.0
    for raw_line in response:
        received_at = time.perf_counter()
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
            data_time = received_at
        elif not line and data_lines:
            yield json.loads("\n".join(data_lines)), data_time
            data_lines = []


@dataclass
class _MessageStream:
    model: str
    started_at: float
    usage: dict[str, int] = field(default_factory=dict)
    ttft_s: float | None = None
    stop_reason: str | None = None
    completed: bool = False

    def accept(self, event: dict[str, Any], received_at: float) -> None:
        # Strings externas são interpretadas somente na borda do protocolo.
        try:
            kind = EventKind(event["type"])
        except (KeyError, ValueError):
            return  # A API pode adicionar eventos novos.

        match kind:
            case EventKind.ERROR:
                raise RuntimeError(str(event.get("error")))
            case EventKind.MESSAGE_START:
                message = event["message"]
                self.model = message.get("model", self.model)
                self.usage.update(message.get("usage") or {})
            case EventKind.CONTENT_DELTA:
                delta = event.get("delta", {})
                if self.ttft_s is None and delta.get("text") and delta.get("type") == DeltaKind.TEXT:
                    self.ttft_s = round(received_at - self.started_at, 6)
            case EventKind.MESSAGE_DELTA:
                self.usage.update(event.get("usage") or {})
                self.stop_reason = event.get("delta", {}).get("stop_reason", self.stop_reason)
            case EventKind.MESSAGE_STOP:
                self.completed = True

    def result(self, status: int, latency_s: float) -> MessageResult:
        if not self.completed:
            raise RuntimeError("Stream terminou sem message_stop")
        input_tokens = self.usage.get("input_tokens", 0)
        cache_created = self.usage.get("cache_creation_input_tokens", 0)
        cache_read = self.usage.get("cache_read_input_tokens", 0)
        return {
            "status": status,
            "model": self.model,
            "ttft_s": self.ttft_s,
            "latency_s": latency_s,
            "stop_reason": self.stop_reason,
            "input_tokens": input_tokens,
            "cache_creation_input_tokens": cache_created,
            "cache_read_input_tokens": cache_read,
            "input_tokens_total": input_tokens + cache_created + cache_read,
            "output_tokens": self.usage.get("output_tokens", 0),
        }


def send_message(api_key: str, model: str, prompt: str, max_tokens: int) -> MessageResult:
    """Envia a mensagem e mede até o primeiro texto e o fim da resposta."""
    body = {
        "model": model,
        "messages": _messages(prompt),
        "max_tokens": max_tokens,
        "stream": True,
    }
    request = _request(api_key, "", body)
    started_at = time.perf_counter()
    stream = _MessageStream(model=model, started_at=started_at)
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        for event, received_at in _stream_events(response):
            stream.accept(event, received_at)
        latency_s = round(time.perf_counter() - started_at, 6)
        return stream.result(response.status, latency_s)
