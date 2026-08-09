# Luna Assistant Prime v1.3.0

Esta versão torna a configuração dos serviços coerente com o Provider Hub:
cada serviço mostra sua rota ordenada e somente os parâmetros dos providers
selecionados, enquanto o painel geral continua sendo a visão consolidada.

## Principais mudanças

- Rota editável dentro de Conversation, AI Task, STT e TTS.
- Select múltiplo pesquisável: digite para filtrar e selecione os providers na
  ordem de execução; os itens aparecem da esquerda para a direita por prioridade.
- Painel geral de rotas e telas dos serviços atualizam o mesmo catálogo central,
  sem manter duas configurações concorrentes.
- Campos dinâmicos: parâmetros Gemini aparecem somente com Google AI na rota;
  campos Speech aparecem somente com Azure na rota.
- AI Task agora possui rota e modelo independentes para geração de Image.
- TTS ganhou voz Google específica para operação principal ou fallback, evitando
  enviar nomes de voz Azure ao Gemini.
- O runtime de TTS, Image e a identificação do dispositivo seguem a prioridade
  da rota central.
- Migração automática e não destrutiva para o esquema `2:11`.

## Migração e compatibilidade

- Rotas, providers, API keys, regiões, limites e histórico de consumo da
  `v1.2.0` são preservados.
- Modelos, prompts, personalidade, temperatura, Top P, Top K e demais opções das
  entidades existentes permanecem intactos.
- O antigo campo interno `provider` continua aceito para compatibilidade, mas
  deixa de decidir a execução; a rota central passa a ser a fonte de verdade.
- Tavily Search, frases de latência, áudio externo, callback do player, barge-in
  e integração com o Luna Satellite permanecem compatíveis.

## Como funciona a nova rota

1. Abra a configuração de uma entidade Conversation, AI Task, STT ou TTS.
2. No campo **Rota de providers**, digite para pesquisar um provider.
3. Selecione os providers na ordem desejada, por exemplo `Azure → Google AI`.
4. A tela é atualizada para exibir somente os parâmetros pertinentes à seleção.
5. Ao salvar, a mesma ordem aparece no painel geral **Rotas dos serviços**.

O painel geral também usa o novo select pesquisável e pode continuar sendo usado
para revisar ou alterar todas as rotas em um só lugar.

## Status de validação

Foram validados sintaxe Python, JSON, migração, selects pesquisáveis, sincronismo
das rotas, exibição condicional, Image separado, fallback de voz TTS e toda a
suíte de regressão incluída. Testes com credenciais reais e reprodução física no
Home Assistant 2026.7.4 ainda são recomendados antes de promover para estável.

## Dados para a release do GitHub

- **Tag:** `v1.3.0`
- **Título:** `Luna Assistant Prime v1.3.0`
- **Commit sugerido:** `[ChatGPT] Luna Assistant Prime v1.3.0: add searchable service routes and provider-aware settings`
- **Tipo inicial recomendado:** pré-release
