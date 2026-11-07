# Benchmark Claude

- `docs/`: plano e relatório do estudo.
- `scripts/`: coleta pela API e análise dos resultados.
- `data/`: medições em CSV.
- `presentation/`: material da apresentação.

Para coletar:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Preencha ANTHROPIC_API_KEY em .env
python scripts/benchmark.py
```
