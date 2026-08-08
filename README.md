# Luna Assistant v0.3.10-stable

## Respostas mais confiáveis

A Luna Conversation aplica uma política global de confiabilidade: não deve inventar
informações, deve pesquisar fatos atuais ou incertos quando a pesquisa estiver
disponível e deve admitir claramente quando não conseguir confirmar uma resposta.

## Conversa contínua segura

Depois de enviar o TTS ao Google Nest, a integração acompanha o estado real do
player. Quando a reprodução muda de `playing`/`buffering` para `idle`, `off` ou
`paused`, ela avisa o Luna Satellite v0.2.3-alpha. O Satellite só então abre o
follow-up automático, caso **Luna Continuous Conversation** esteja ligado.

## Interrupção por “Ei, Luna”

A integração registra a ação `luna_assistant.interrupt_external_audio`. O
firmware Luna Satellite v0.1.5 chama essa ação assim que o modelo local detecta
a wake word. A ação localiza automaticamente o Google Nest ou outro
`media_player` selecionado nas opções da conversa e interrompe a reprodução.

No dispositivo ESPHome, habilite **Permitir que o dispositivo execute ações do
Home Assistant** na configuração da integração ESPHome. Sem essa permissão, o
ATOM detectará a wake word, mas não poderá solicitar a interrupção do Nest.

Correção do microfone durante respostas reproduzidas em Google Nest ou outro
`media_player` externo.

## O que foi corrigido

Na v0.3.5, o serviço TTS externo era chamado corretamente, mas o Assist podia
encerrar o turno antes de o Google Nest terminar de falar. O Luna Satellite
entrava imediatamente no modo de continuação e o microfone acabava ouvindo a
própria resposta da Luna.

A v0.3.8 libera o Assist Pipeline assim que o Google Nest começa a resposta.
O Luna Satellite volta então ao `micro_wake_word`, não ao reconhecimento livre
de fala. Ruídos comuns e a própria voz do Nest não iniciam STT. Somente a wake
word local “Ei, Luna” interrompe o player e abre um novo turno.

## Roteamento por entity_id

O destino continua sendo sempre o `entity_id` canônico selecionado no Home
Assistant, por exemplo:

```text
media_player.google_nest
```

O nome amigável mostrado na interface, como `Google Nest`, não é enviado ao
serviço TTS.

## Ordem de roteamento externo

1. Microsoft TTS: `tts.microsoft_say`.
2. Luna TTS: `tts.speak`, caso o serviço Microsoft não exista ou falhe.
3. Atom: a fala original do Assist Pipeline é preservada se nenhuma rota
   externa for aceita.

## Instalação

1. Substitua a pasta `custom_components/luna_assistant` pela desta versão.
2. Reinicie completamente o Home Assistant.
3. Mantenha o Google Nest selecionado em **Luna Conversation → Configurar**.
4. Faça uma pergunta e produza algum som perto do Atom enquanto o Nest fala.
5. O follow-up deve abrir somente depois que a fala externa terminar.

## Compatibilidade

- Home Assistant alvo: 2026.7.4.
- Microsoft Text-to-Speech por `tts.microsoft_say`.
- Luna TTS por `tts.speak` como fallback.
- Firmware recomendado: Luna Satellite v0.2.3-alpha.
- Não há migração de configuração; minor version permanece 6.
