# Changelog

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
