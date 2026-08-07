# Changelog

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
