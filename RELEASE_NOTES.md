# Luna Assistant v0.3.8

**Tag:** `v0.3.8`  
**Título:** `Luna Assistant v0.3.8 – Conversa contínua segura no Google Nest`  
**Asset:** `luna-assistant-v0.3.8-stable.zip`

## Conversa contínua restaurada

A integração agora acompanha o estado real do Google Nest após enviar o TTS.
Quando o player termina, ela chama a ação do Luna Satellite `v0.2.3-alpha`,
que abre automaticamente o próximo turno se **Luna Continuous Conversation**
estiver ligado.

Enquanto o Nest fala, o Satellite mantém somente o detector local de wake word.
Ruídos e a voz do Nest não são enviados ao STT.

## Interrupção natural por wake word

O firmware Luna Satellite chama a ação
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

Requer Luna Satellite `v0.2.3-alpha` para restaurar a conversa contínua segura.
# Luna Assistant v0.3.9-stable

Esta versão adiciona pesquisa seletiva na internet à Luna Conversation por
meio do Google Search Grounding. O Gemini decide quando uma pergunta exige
informações atuais; perguntas estáveis continuam sendo respondidas sem busca.

A pesquisa pode permanecer habilitada junto com a API Assist do Home
Assistant, portanto a mesma Luna continua controlando a casa. Ela também está
disponível no perfil de latência Rápido.

Para uma Luna Conversation já existente, abra **Reconfigurar**, ative
**Pesquisa na internet (Google Search)** e salve. Novas entidades de conversa
já recebem a opção habilitada.

Exemplos para teste:

- "Luna, pesquise as notícias de hoje."
- "Qual foi o último resultado do Palmeiras?"
- "Vai chover amanhã em São Paulo?"
- "Acenda a luz da sala e depois me diga a previsão do tempo."

O Google contabiliza as consultas de Search Grounding separadamente conforme
as regras e cotas do projeto Gemini configurado.
