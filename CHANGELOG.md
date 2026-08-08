# Changelog

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
