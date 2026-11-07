"""Coleta sequencial de tokens, TTFT e latência da API Claude."""

import csv
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

from anthropic_api import API_VERSION, count_input_tokens, send_message

MODELS: list[str] = [
    "claude-haiku-5-5",
    "claude-sonnet-5-5",
    "claude-opus-5-5",
]
REPETITIONS = 5
INTERVAL_SECONDS = 5
MAX_TOKENS = 32
CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "measurements.csv"

INSTRUCTION = "Leia o texto abaixo e responda somente: Recebido.\n\n"
TEXT = (
    "A biblioteca abre pela manhã. Os livros ficam organizados em estantes. "
    "Uma mesa fica perto da janela. O ambiente é silencioso e bem iluminado. "
    "As pessoas podem consultar o catálogo e escolher um livro para leitura. "
    "Ao final do dia, os livros retornam às estantes. "
)
PROMPTS: dict[str, str] = {
    "curto": INSTRUCTION + TEXT * 4,
    "medio": INSTRUCTION + TEXT * 16,
    "longo": INSTRUCTION + TEXT * 64,
}

FIELDS: list[str] = [
    "timestamp_utc", "prompt", "repetition", "model", "api_version",
    "latency_s", "ttft_s", "counted_input_tokens", "status", "input_tokens", "cache_creation_input_tokens",
    "cache_read_input_tokens", "input_tokens_total", "output_tokens",
    "max_tokens", "stop_reason", "error",
]


def measure(
    api_key: str, model: str, name: str, prompt: str, repetition: int, counted_input_tokens: int
) -> dict[str, object]:
    row: dict[str, object] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prompt": name, "repetition": repetition,
        "model": model, "api_version": API_VERSION, "max_tokens": MAX_TOKENS,
        "counted_input_tokens": counted_input_tokens,
    }
    start = time.perf_counter()
    try:
        row.update(send_message(api_key, model, prompt, MAX_TOKENS))
    except HTTPError as exc:
        row["status"] = exc.code
        row["error"] = f"HTTP {exc.code}"
    except (URLError, TimeoutError) as exc:
        row["status"] = "network_error"
        row["error"] = type(exc).__name__
    except (RuntimeError, ValueError) as exc:
        row["status"] = "stream_error"
        row["error"] = str(exc)
    finally:
        row.setdefault("latency_s", round(time.perf_counter() - start, 6))
    return row


def main() -> None:
    load_dotenv(CSV_PATH.parents[1] / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        raise SystemExit("Defina ANTHROPIC_API_KEY antes de executar.")

    # A contagem é feita uma vez por prompt, fora das latências medidas.
    counted_inputs = {
        (model, name): count_input_tokens(api_key, model, prompt)
        for model in MODELS
        for name, prompt in PROMPTS.items()
    }

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)

        if file.tell() == 0:
            writer.writeheader()

        for model in MODELS:
            rng = random.Random(42)

            for repetition in range(1, REPETITIONS + 1):

                names = list(PROMPTS)

                rng.shuffle(names)

                for name in names:
                    prompt = PROMPTS[name]
                    row = measure(api_key, model, name, prompt, repetition, counted_inputs[(model, name)])
                    writer.writerow(row)
                    file.flush()
                    print(f"{model} | {name} {repetition}/{REPETITIONS}: {row['status']} em {row['latency_s']:.3f}s")
                    time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
