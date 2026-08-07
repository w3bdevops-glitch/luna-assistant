# Luna Assistant v0.3.5

**Tag:** `v0.3.5`  
**Título:** `Luna Assistant v0.3.5`  
**Asset:** `luna-assistant-v0.3.5-stable.zip`

## Correção principal

O modo Google Nest/Outro media player agora usa o serviço
`tts.microsoft_say` quando ele está disponível. A chamada recebe diretamente
o `entity_id` selecionado no Home Assistant, como `media_player.nest_sala`.
O nome amigável do dispositivo não participa do roteamento.

## Fallback

- Microsoft TTS falhou ou não existe: tenta Luna TTS por `tts.speak`.
- Nenhuma rota externa foi aceita: mantém a resposta no Atom.

## Instalação

Substitua `custom_components/luna_assistant`, reinicie o Home Assistant e teste
uma conversa pelo satélite com a saída externa selecionada.

Não há atualização de firmware nesta versão.
