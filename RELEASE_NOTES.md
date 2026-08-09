# Luna Assistant Prime v1.2.0

Esta versão reorganiza o Provider Hub, adiciona Tavily Search e entrega feedback
de voz durante pesquisas demoradas.

## Principais mudanças

- Um provider por tecnologia, com listas independentes e ilimitadas de chaves.
- Rotas ordenadas por capacidade e failover entre providers compatíveis.
- Seleção pela maior estimativa de saldo ou round-robin.
- Limites gerais/por provider, cooldown por chave e máximo total de tentativas.
- Medição persistente de chamadas, tokens, caracteres, segundos e créditos.
- Tavily Search disponível como ferramenta nativa em AI Task e Conversation.
- Flag geral **Habilitar pesquisa na internet**, ligada por padrão.
- Cinco frases configuráveis de latência com geração TTS antecipada, cache,
  escolha aleatória sem repetição imediata e pré-visualização.
- Migração automática e não destrutiva para o esquema 2:10.

## Migração e compatibilidade

- Todas as instâncias antigas da mesma tecnologia são consolidadas, preservando
  as credenciais e seus IDs.
- Rotas legadas são convertidas para os providers tecnológicos correspondentes.
- O antigo controle de Google Search por Conversation torna-se a nova chave
  geral. Sem valor anterior explícito, a pesquisa fica ligada.
- AI Task, Conversation, STT, TTS, Image, áudio externo, callback do player e
  barge-in permanecem compatíveis.
- Para usar pesquisa após a atualização, cadastre uma chave Tavily e confirme a
  rota Search.

## Segurança e limites

- Segredos não aparecem nos diagnósticos; somente sufixos mascarados.
- `0` significa ilimitado para cotas e tentar todas as opções para tentativas.
- Contadores locais ajudam a controlar consumo, mas não substituem a cota e o
  faturamento oficiais dos providers.

## Status de validação

Sintaxe, formatação, JSON, migração, seleção de credenciais, limites, failover,
Tavily, ferramenta Search, frases de latência e regressões de áudio foram
validados sem credenciais. Recomenda-se publicar inicialmente como **pré-release**
até concluir testes reais no Home Assistant 2026.7.4 com Google, Azure, Tavily,
Atom e os media players utilizados.

## Dados para a release do GitHub

- **Tag:** `v1.2.0`
- **Título:** `Luna Assistant Prime v1.2.0`
- **Commit sugerido:** `[ChatGPT] Luna Assistant Prime v1.2.0: add provider routes, Tavily Search and latency feedback`
- **Tipo inicial recomendado:** pré-release
