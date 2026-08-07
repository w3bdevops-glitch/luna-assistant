# Luna Assistant v0.3.7

**Tag:** `v0.3.7`  
**Título:** `Luna Assistant v0.3.7`  
**Asset:** `luna-assistant-v0.3.7-stable.zip`

## Interrupção natural por wake word

O firmware Luna Satellite v0.1.5 chama a nova ação
`luna_assistant.interrupt_external_audio` no instante em que “Ei, Luna” é
detectado. A integração identifica o Google Nest ou outro player configurado,
interrompe a resposta anterior e permite que o satélite abra um novo turno.

É necessário permitir que o dispositivo ESPHome execute ações do Home
Assistant nas opções da integração ESPHome.

## Fluxo durante a resposta

Depois que o TTS externo começa, o Assist Pipeline é liberado e o Luna
Satellite retorna exclusivamente ao modelo local de wake word. A própria voz
do Nest e ruídos do ambiente não iniciam reconhecimento de conversa. Ao ouvir
“Ei, Luna”, o firmware interrompe o player, encerra qualquer turno anterior e
abre uma nova escuta.

## Garantia do destino

A chamada usa somente o `entity_id` canônico retornado pelo
Home Assistant, como `media_player.google_nest`. O nome amigável do aparelho
não é utilizado.

## Fallbacks

- Microsoft TTS indisponível: Luna TTS por `tts.speak`.
- Nenhuma rota externa aceita: resposta preservada no Atom.

## Instalação

Substitua `custom_components/luna_assistant`, reinicie o Home Assistant e teste
uma conversa pelo satélite com a saída externa selecionada.

Não há atualização de firmware nesta versão.
