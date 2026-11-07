# Plano do estudo — desempenho da API Claude

**Estado:** proposta, sem experimentos executados. Modelo, orçamento e limites da conta devem ser confirmados antes da coleta.

## Sistema e pergunta

Será avaliada a API de mensagens da Anthropic (`POST /v1/messages`) com o modelo **Claude Haiku 4.5**, identificador fixo proposto `claude-haiku-4-5-20251001`. A [documentação oficial](https://platform.claude.com/docs/en/models/haiku-4-5/overview) informa esse identificador; sua disponibilidade deve ser verificada antes do experimento. O hardware remoto não é divulgado, portanto o estudo observa o serviço como caixa-preta, incluindo rede e filas na latência medida pelo cliente.

**Pergunta:** como o número de tokens de entrada afeta a latência total e a vazão efetiva de saída em requisições sequenciais com resposta curta? Com que precisão um modelo ajustado nos prompts curto e longo prevê a latência do prompt médio?

As técnicas escolhidas são **monitoramento**, para obter medições reais, e **modelo analítico**, para prever e confrontar essas medições.

## Desenho experimental

| Elemento | Definição proposta |
| --- | --- |
| Entrada | Três prompts fixos e versionados, com a **mesma instrução e tarefa**; apenas a extensão de um texto neutro muda. Sem dados pessoais. Usar a [API de contagem de tokens](https://platform.claude.com/docs/en/api/messages/count_tokens) para aproximar cada alvo (±5%). A análise usa os tokens efetivamente informados na resposta. |
| Tamanhos | Curto: 256 tokens; médio: 1.024; longo: 4.096. Curto e longo ajustam o modelo; médio fica reservado para validação. |
| Repetições | Cinco por tamanho inicialmente (15 chamadas medidas). Ampliar até dez por tamanho se o piloto mostrar alta dispersão, respeitando o orçamento. Executar uma chamada por vez e embaralhar a ordem em cada rodada. |
| Controles | Mesmo modelo, instrução e formato; resposta curta; `max_tokens=32`; com streaming, sem ferramentas ou cache configurado. Registrar tokens de saída e campos de cache. |
| Latência | Segundos entre o início da chamada e o recebimento completo da resposta, usando relógio monotônico do cliente. |
| Tempo até o primeiro texto (TTFT) | Segundos entre o início da chamada e o primeiro evento `text_delta` não vazio recebido por streaming. Um evento pode conter mais de um token. |
| Vazão efetiva | `output_tokens / latency_s`. Inclui rede e espera; não representa a velocidade isolada de geração nem requisições por segundo. |

Um piloto verificará acesso, estabilidade do tamanho das respostas, duração e limites da conta. As chamadas terão intervalo inicialmente de 5 segundos, ajustado aos limites reais de requisições e tokens por minuto. Registrar cada tentativa, inclusive erros e novas tentativas, em CSV; não incluir espera de retry na latência de uma chamada bem-sucedida. Prompts repetidos podem produzir leituras de cache; registrar seus campos de uso e separar essas observações, assim como respostas truncadas. A [documentação de limites e uso](https://platform.claude.com/docs/en/api/rate-limits) orienta esses registros.

## Modelo analítico

O modelo soma uma parcela fixa, o tempo associado aos tokens de entrada e uma variação aleatória:

$$
L(n) = \alpha + \beta n + \frac{D}{1000}
$$

**Parâmetros:**

- $L(n)$: latência da chamada, em segundos.
- $n$: número efetivo de tokens de entrada.
- $\alpha$: parcela fixa estimada pela reta, em segundos.
- $\beta$: aumento estimado da latência por token de entrada, em segundos por token.
- $D$: variação aleatória, em milissegundos. Pode aumentar ou diminuir a latência prevista. A divisão por 1.000 converte esse valor para segundos.

As medições dos prompts curto e longo definem a reta: suas repetições são usadas para estimar $\alpha$ e $\beta$. O maior desvio observado em relação à reta define a escala de $D$; para explorar cenários, sorteamos valores uniformemente entre o negativo e o positivo desse desvio, convertido para milissegundos. Essa escolha é ilustrativa: não afirma que a API siga essa distribuição nem garante um limite para chamadas futuras.

## Comparação com as medições

Com os parâmetros fixados, calcular a previsão linear para a média de tokens de entrada do prompt médio e compará-la com a **média das latências medidas** desse prompt. Relatar a diferença absoluta em segundos e como percentual da média medida. Mostrar os valores individuais para descrever a variação observada e usar a faixa de $D$ apenas como ilustração dos cenários do modelo. Registrar diferenças nos tokens de saída, que também afetam a latência. O prompt médio valida apenas **um ponto de interpolação**.

## Reprodução, custo e limites

Registrar data e horário, ambiente cliente, versões de Python/SDK, modelo solicitado e retornado, parâmetros, identificador do prompt, ordem, tokens, latência, erros e campos de cache. Guardar a chave somente na variável de ambiente `ANTHROPIC_API_KEY`. Antes da coleta, calcular o teto de gasto com os [preços oficiais](https://platform.claude.com/docs/en/about-claude/pricing):

$$
C \approx \frac{\sum_{i=1}^{N} (n_i p_{\text{entrada}} + o_i p_{\text{saída}})}{10^6}
$$

Somar piloto e margem para falhas. O orçamento ainda não foi definido. Rede, carga remota, variação do tamanho das respostas e número reduzido de repetições limitam as conclusões. O relatório final registrará eventuais mudanças neste plano.
