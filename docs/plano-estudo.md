# Plano do estudo — desempenho da API Claude

**Estado:** experimentos executados (`data/measurements.csv`). Coleta realizada com os modelos da família Claude 5.5 (`claude-haiku-5-5`, `claude-sonnet-5-5` e `claude-opus-5-5`).

## Sistema e pergunta

Será avaliada a API de mensagens da Anthropic (`POST /v1/messages`) em três modelos da família **Claude 5.5**: **Claude Haiku 5.5** (`claude-haiku-5-5`), **Claude Sonnet 5.5** (`claude-sonnet-5-5`) e **Claude Opus 5.5** (`claude-opus-5-5`). O hardware remoto não é divulgado, portanto o estudo observa o serviço como caixa-preta, incluindo rede e filas na latência medida pelo cliente.

**Pergunta:** como o número de tokens de entrada e o porte do modelo afetam a latência total e a vazão efetiva de saída em requisições sequenciais com resposta curta? Com que precisão um modelo analítico linear ajustado nos prompts curto e longo de cada modelo prevê a latência do prompt médio?

As técnicas escolhidas são **monitoramento**, para obter medições reais, e **modelo analítico**, para prever e confrontar essas medições.

## Desenho experimental

| Elemento | Definição |
| --- | --- |
| Entrada | Três prompts fixos e versionados (`curto`, `medio`, `longo`), com a **mesma instrução e tarefa** (`Leia o texto abaixo e responda somente: Recebido.`); apenas a repetição de um texto neutro muda na proporção $1\times : 4\times : 16\times$ ($4$, $16$ e $64$ repetições do bloco base). Sem dados pessoais. Usar a [API de contagem de tokens](https://platform.claude.com/docs/en/api/messages/count_tokens) antes da bateria medida e confirmar os tokens efetivamente informados na resposta. |
| Tamanhos | Curto: 458 tokens; médio: 1.742 tokens; longo: 6.878 tokens (alvos iniciais de referência: 256, 1.024 e 4.096). Curto e longo ajustam o modelo de cada variante; médio fica reservado para validação. |
| Repetições | Cinco por tamanho para cada um dos três modelos (15 chamadas por modelo, 45 chamadas medidas no total). Executar uma chamada por vez e embaralhar a ordem dos três tamanhos em cada rodada (`seed=42`). |
| Controles | Mesma instrução e formato (`anthropic-version: 2023-06-01`); resposta curta (`output_tokens = 7`, `stop_reason = end_turn`); `max_tokens=32`; com streaming, sem ferramentas ou cache configurado. Registrar tokens de saída e campos de cache. |
| Latência | Segundos entre o início da chamada e o recebimento completo da resposta, usando relógio monotônico do cliente (`time.perf_counter`). |
| Tempo até o primeiro texto (TTFT) | Segundos entre o início da chamada e o primeiro evento `text_delta` não vazio recebido por streaming. Um evento pode conter mais de um token. |
| Vazão efetiva | `output_tokens / latency_s`. Inclui rede e espera; não representa a velocidade isolada de geração nem requisições por segundo. |

As chamadas são espaçadas por um intervalo fixo de 5 segundos para respeitar os limites de requisições e tokens por minuto da conta. Cada tentativa, inclusive eventuais erros, é registrada em `data/measurements.csv`. Prompts repetidos poderiam produzir leituras de cache; por isso os campos `cache_creation_input_tokens` e `cache_read_input_tokens` são registrados em todas as observações, assim como o motivo de parada (`stop_reason`). A [documentação de limites e uso](https://platform.claude.com/docs/en/api/rate-limits) orienta esses registros.

## Modelo analítico

Para cada modelo avaliado (`claude-haiku-5-5`, `claude-sonnet-5-5` e `claude-opus-5-5`), o modelo analítico soma uma parcela fixa, o tempo associado aos tokens de entrada e uma variação aleatória:

$$
L(n) = \alpha + \beta n + \frac{D}{1000}
$$

**Parâmetros:**

- $L(n)$: latência da chamada, em segundos.
- $n$: número efetivo de tokens de entrada (`458`, `1.742` ou `6.878`).
- $\alpha$: parcela fixa estimada pela reta (rede, fila inicial e geração da resposta curta constante de 7 tokens), em segundos.
- $\beta$: aumento estimado da latência por token de entrada, em segundos por token.
- $D$: variação aleatória, em milissegundos. Pode aumentar ou diminuir a latência prevista. A divisão por 1.000 converte esse valor para segundos.

As medições dos prompts curto ($n = 458$) e longo ($n = 6.878$) de cada modelo definem a reta: suas repetições são usadas para estimar $\alpha$ e $\beta$. O maior desvio absoluto observado nas repetições de treino (curto e longo) em relação à reta define a escala $D_{\max}$; para explorar cenários, sorteamos valores uniformemente em $[-D_{\max}, +D_{\max}]$, convertidos para milissegundos. Essa escolha é ilustrativa: não afirma que a API siga essa distribuição nem garante um limite para chamadas futuras.

## Comparação com as medições

Com os parâmetros fixados para cada modelo, calcular a previsão linear $\hat{L}(1.742) = \alpha + 1.742\beta$ para o prompt médio e compará-la com a **média das latências medidas** desse prompt. Relatar a diferença absoluta em segundos e como percentual da média medida. Mostrar os valores individuais para descrever a variação observada e usar a faixa $\hat{L}(n) \pm D_{\max}/1000$ como ilustração dos cenários do modelo (avaliando também se a variação aleatória $D$ domina a inclinação $\beta n$ em modelos mais rápidos, como o Haiku, em contraste com modelos maiores, como Sonnet e Opus). Verificar a estabilidade dos tokens de saída (`output_tokens`) e a ausência de leituras de cache. O prompt médio valida apenas **um ponto de interpolação** por modelo.

## Reprodução, custo e limites

Registrar data e horário UTC, versão da API, modelo, identificador do prompt, repetição, tokens contados e efetivos, latência total, TTFT, vazão, motivo de parada, erros e campos de cache. Guardar a chave somente na variável de ambiente `ANTHROPIC_API_KEY`. O gasto das chamadas é estimado com os [preços oficiais](https://platform.claude.com/docs/en/about-claude/pricing):

$$
C \approx \frac{\sum_{i=1}^{N} (n_i p_{\text{entrada}} + o_i p_{\text{saída}})}{10^6}
$$

Rede, carga remota, sublinearidade do processamento em lote (*prefill*) na GPU e número reduzido de repetições (5 por combinação de modelo e tamanho) limitam as conclusões. O relatório final consolidará os parâmetros ajustados e a validação experimental.
