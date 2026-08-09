# Changelog

## 1.3.0-prime

- Adicionada a rota de providers diretamente na configuração de Conversation,
  AI Task, STT e TTS, sem duplicar o armazenamento central.
- Substituída a digitação manual de IDs por selects múltiplos pesquisáveis; os
  itens selecionados preservam a ordem de prioridade da esquerda para a direita.
- Mantido o painel geral de rotas como visão consolidada e editável da mesma
  configuração usada nos serviços.
- A tela de cada serviço agora mostra apenas parâmetros compatíveis com os
  providers presentes em sua rota.
- Adicionadas rota e modelo de Image separados na configuração de AI Task.
- Adicionada voz Google TTS específica para uso principal ou fallback, sem
  reutilizar incorretamente uma voz Azure no Gemini.
- O runtime de TTS, Image e os dados de dispositivo agora seguem a rota central,
  sem depender do antigo campo fixo `provider` da entidade.
- Migração não destrutiva para config entry minor version 11, preservando rotas,
  entidades, prompts, modelos, credenciais, limites e consumo existentes.
- Atualizados diagnósticos de pacote, traduções e testes de regressão.

## 1.2.0-prime

- Substituídas instâncias duplicadas por um catálogo fixo de tecnologias:
  Google Gemini, Microsoft Azure Speech e Tavily.
- Adicionadas rotas centrais e ordenadas para AI Task, Conversation, STT, TTS,
  Search e Image.
- Adicionada rotação por maior saldo estimado ou round-robin, com desempate
  distribuído, cooldown individual e limite total de tentativas por operação.
- Adicionado Tavily Search com múltiplas chaves, profundidade basic/advanced,
  limite de resultados e contabilidade de créditos.
- Adicionada flag geral **Habilitar pesquisa na internet**, ligada por padrão e
  aplicada a AI Task e Conversation.
- Removido o controle de Search por Conversation; o valor legado é migrado para
  a configuração geral.
- Adicionadas cinco frases configuráveis para mascarar latência da pesquisa,
  geração TTS antecipada, cache por hash, reprodução aleatória sem repetição e
  pré-visualização.
- Adicionados serviços para gerar e pré-visualizar frases de latência.
- Migração não destrutiva para config entry minor version 10, preservando
  credenciais, IDs, regiões e rotas legadas.
- Atualizados diagnósticos, traduções, documentação e testes de regressão.

## 1.1.1-prime

- Corrigida a interface para exibir listas independentes por provider.
- Adicionado catálogo visual de API keys do Google Gemini, sem limite fixo.
- Adicionado catálogo visual de credenciais Microsoft Azure, cada uma com chave
  Speech e região próprias, sem limite fixo.
- Após adicionar, editar ou remover uma credencial, o fluxo retorna à lista do
  mesmo provider para permitir cadastros consecutivos.
- Adicionada proteção contra credenciais duplicadas dentro do mesmo provider.
- Mantidos rotação, prioridade, limites e consumo individual de cada chave.
- Config entry minor version 9, preservando todas as credenciais e históricos da
  v1.1.0 sem regravação destrutiva.

## 1.1.0-prime

- Criado gerenciador central de múltiplas API keys Google e Azure.
- Adicionados cadastro, edição, ativação, prioridade e remoção pela interface.
- Adicionados limites diários/mensais de chamadas por chave e por provedor.
- Adicionados limites de tokens Google, caracteres Azure TTS e segundos Azure STT.
- Adicionadas rotação por prioridade, round-robin e menor consumo mensal.
- Adicionados failover automático, máximo de tentativas e cooldown por chave.
- Adicionado failover entre Google e Azure para STT/TTS após esgotar as chaves
  elegíveis do provedor preferido.
- Consumo persistido no Home Assistant e exposto sem segredos nos diagnósticos.
- Adicionado Microsoft Azure Speech-to-Text para WAV/PCM e OGG/Opus em 16 kHz.
- Google AI Task, Conversation, STT, TTS e imagem passaram pelo mesmo controle.
- Config entry minor version 8 com migração das chaves da Prime v1.0/0.3.x.

## 1.0.0-prime

- Criado Luna Core, sem assumir responsabilidades do Assist/Satellite.
- Criado Provider Hub plugável com contrato, registro e capacidades.
- Google Gemini disponível para AI Task, Conversation, STT e TTS.
- Azure Speech adicionado como provedor TTS nativo com SSML e WAV PCM.
- Criado Tools Hub com Google Search Grounding e ferramentas HA simultâneas.
- Adicionadas métricas internas e normalização de erros.
- Adicionada seleção explícita da entidade Luna TTS para áudio externo.
- Config entry minor version 7 com migração não destrutiva.
- Mantidas todas as correções da série 0.3.x.

## 0.3.10-stable

- Adicionada política global e obrigatória de confiabilidade à Luna Conversation.
- A Luna foi instruída a nunca inventar fatos, nomes, números, datas, receitas,
  resultados ou fontes, independentemente do perfil de latência ou personalidade.
- Informações atuais, específicas, verificáveis ou incertas devem acionar a pesquisa
  na internet quando ela estiver disponível.
- Quando não houver confirmação suficiente, a Luna deve admitir que não sabe; se a
  pesquisa falhar, deve informar que não conseguiu confirmar naquele momento.
- Fatos confirmados, hipóteses, sugestões e criações devem ser diferenciados.
- Mantidos o Google Search Grounding e todo o comportamento de áudio da `v0.3.9`.

## 0.3.9-stable

- Ativada a pesquisa seletiva na internet com Google Search Grounding.
- A Luna pode pesquisar informações atuais e controlar o Home Assistant na
  mesma conversa usando a combinação de ferramentas suportada pelo Gemini 3.
- A pesquisa agora funciona também no perfil Rápido.
- Novas entidades Luna Conversation recebem a pesquisa habilitada por padrão;
  entidades existentes podem ativá-la em Reconfigurar.
- Mantido todo o comportamento de áudio e barge-in da `v0.3.8-stable`.

## 0.3.8-stable

- Adicionado acompanhamento do estado do Google Nest/player externo após o TTS.
- Ao observar a transição real de `playing`/`buffering` para `idle`, `off` ou
  `paused`, a integração notifica o Luna Satellite pelo serviço ESPHome.
- A notificação permite restaurar a conversa contínua sem expor o STT à voz do
  Nest ou a ruídos durante a resposta.
- Mantida a interrupção por wake word introduzida na `v0.3.7`.
- Compatível com Luna Satellite `v0.2.3-alpha`.

## 0.3.7-stable

- Adicionada a ação `luna_assistant.interrupt_external_audio` para barge-in.
- A ação descobre automaticamente os players externos configurados e executa
  `media_player.media_stop` sem exigir um `entity_id` no firmware.
- Compatível com o Luna Satellite v0.1.5, que interrompe a resposta ao detectar
  localmente “Ei, Luna” e inicia um novo turno de escuta.

## 0.3.6-stable

- Impedido o follow-up do satélite enquanto o Google Nest ainda está falando.
- Adicionado rastreamento do `media_player` externo antes da chamada TTS.
- O Assist Pipeline permanece aberto durante os estados `buffering` e `playing`.
- Adicionada margem acústica de 500 ms após o fim da reprodução.
- Adicionado fallback temporal para players que não publicam estado confiável.
- Mantido o uso exclusivo do `entity_id` canônico; nomes amigáveis não são usados.
- Mantido o roteamento Microsoft TTS → Luna TTS → Atom.
- Sem mudança de esquema; config entry minor version permanece 6.

## 0.3.5-stable

- Corrigido o áudio externo com Microsoft Text-to-Speech.
- Adicionado roteamento preferencial por `tts.microsoft_say`.
- Garantido que o alvo seja o `entity_id` canônico do `media_player`, nunca o
  nome amigável do Google Nest.
- Corrigida a referência ausente a `LOGGER` no caminho externo.
- Mantido fallback Microsoft TTS → Luna TTS → Atom.
- Mantida a prevenção de áudio duplicado: o Atom só é silenciado após uma
  chamada externa bem-sucedida.
- Sem mudança de esquema; config entry minor version permanece 6.

## 0.3.4-stable

- Restaurada a seleção de saída na Luna Conversation.
- Adicionadas opções Atom, Google Nest e Outro media player.
- Adicionado seletor de entidade media_player.
- Roteamento externo feito exclusivamente no Home Assistant.
- Firmware não precisa de modo de alto-falante externo.
- Fallback para Atom quando alvo/TTS falha de forma síncrona.
- Prevenção de áudio duplicado: Atom é silenciado somente após `tts.speak`
  ser aceito.
- Conversas digitadas sem contexto de satélite não disparam áudio externo.
- Config entry minor version atualizado para 6.

## 0.3.3-stable

- Perfil Rápido aplicado em tempo de execução.
- TTS Gemini 3.1 com uma chamada e validação WAV.
