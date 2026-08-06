# Luna Assistant v0.3.4-stable

Correção da seleção de saída de áudio. O firmware continua sem qualquer modo
de alto-falante externo; o roteamento fica somente na Luna Assistant.

## Saídas disponíveis em Luna Conversation

- **Atom** — resposta pelo Assist Pipeline normal do satélite.
- **Google Nest** — resposta enviada ao `media_player` do Nest selecionado.
- **Outro media player** — resposta enviada a qualquer entidade `media_player`
  compatível com `tts.speak`.

Para Google Nest ou Outro media player, o campo **Media player de saída** é
obrigatório.

## Como o fallback funciona

1. A Luna gera a resposta.
2. A integração chama `tts.speak` usando a entidade Luna TTS e o media player.
3. Somente quando essa chamada é aceita, a fala do pipeline do Atom é removida.
4. Se o alvo não existir, estiver indisponível ou a chamada gerar erro, a fala
   original permanece e o Atom reproduz a resposta.

Limitação: se o Google Nest aceitar o comando e falhar depois, de forma
assíncrona, o Home Assistant não fornece uma confirmação de reprodução real;
nesse caso específico não é possível voltar automaticamente ao Atom.

## Uso

1. Instale a pasta `custom_components/luna_assistant`.
2. Reinicie completamente o Home Assistant.
3. Abra **Luna Assistant → Luna Conversation → Configurar**.
4. Escolha **Saída de áudio**.
5. Para Nest ou outro player, escolha **Media player de saída**.
6. Mantenha **Perfil de latência: Rápido** para menor tempo de resposta.

## O que permanece da v0.3.3

- Gemini 3.1 Flash Lite no perfil Rápido.
- TTS Gemini 3.1.
- Uma única chamada ao Gemini TTS.
- Validação PCM/WAV.
- Logs separados da API e criação do WAV.
