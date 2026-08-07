# Luna Assistant v0.3.5-stable

Correção do áudio externo para Google Nest e outros `media_player`.

## O que foi corrigido

- A integração agora usa `tts.microsoft_say` quando o Microsoft Text-to-Speech
  está configurado no Home Assistant.
- O destino enviado ao serviço é sempre o `entity_id` real selecionado, por
  exemplo `media_player.nest_sala`.
- O nome amigável mostrado na interface, por exemplo `Google Nest Sala`, nunca
  é usado na chamada do serviço.
- Corrigido o logger ausente no caminho de áudio externo.
- Mantido o fallback automático para Luna TTS e, por último, para o Atom.

## Ordem de roteamento externo

1. Microsoft TTS: `tts.microsoft_say`.
2. Luna TTS: `tts.speak`, caso o serviço Microsoft não exista ou falhe.
3. Atom: a fala original do Assist Pipeline é preservada se nenhuma rota
   externa for aceita.

A resposta do Atom só é removida depois que uma chamada externa termina sem
erro síncrono. Isso evita silêncio quando o serviço TTS ou o player não estão
disponíveis.

## Configuração

Nenhuma migração ou alteração de firmware é necessária.

1. Instale a pasta `custom_components/luna_assistant` desta versão.
2. Reinicie completamente o Home Assistant.
3. Abra **Luna Assistant → Luna Conversation → Configurar**.
4. Escolha **Google Nest** ou **Outro media player**.
5. Em **Media player de saída**, selecione a entidade desejada.

O seletor do Home Assistant grava o `entity_id`; a integração confirma o alvo
no registro de estados antes de chamar o TTS.

## Compatibilidade

- Home Assistant alvo: 2026.7.4.
- Microsoft Text-to-Speech configurado por YAML: suportado por
  `tts.microsoft_say`.
- Luna TTS continua disponível como fallback.
- Firmware Luna Satellite permanece na v0.1.6-stable.
