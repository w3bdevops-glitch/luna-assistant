# Luna Assistant Prime v1.0.0

Integração personalizada para o Home Assistant 2026.7 que fornece serviços de
IA ao Assist Pipeline sem substituir sua orquestração nativa.

## Arquitetura preservada

- **Luna Satellite / ESPHome**: hardware, wake word, botões, I²S, estados e
  experiência de voz no Atom.
- **Home Assistant Assist**: orquestra `STT → Conversation → TTS`.
- **Luna Assistant Prime**: entidades de IA, personalidade, ferramentas,
  provedores e roteamento de áudio externo.

Luna Core não controla microfone, wake word, sessão do Satellite nem barramento
I²S.

## Entregue na Prime v1

### Luna Core

Raiz de execução interna que inicializa e conecta o Provider Hub, Tools Hub e
métricas operacionais. Credenciais nunca são incluídas nos diagnósticos.

### Luna Provider Hub

Registro plugável por capacidade. A entidade do Home Assistant solicita uma
capacidade e o Hub seleciona o adaptador configurado.

| Provedor | AI Task | Conversation | STT | TTS |
|---|---:|---:|---:|---:|
| Google Gemini | Sim | Sim | Sim | Sim |
| Microsoft Azure Speech | Não | Não | Não | Sim |

O Google mantém seleção de modelos e fornece Gemini 3.1 Flash-Lite,
transcrição multimodal e Gemini 3.1 Flash TTS. O Azure TTS usa a API regional
Speech, SSML e áudio WAV PCM validado.

### Luna Tools Hub

Primeiro adaptador de ferramenta: Google Search Grounding. A pesquisa pode ser
combinada com as funções de controle do Home Assistant na mesma conversa e
continua disponível no perfil Rápido.

### Métricas internas

Registra chamadas, sucesso, erro normalizado, unidades de entrada/saída e
latência recente (última, média, p50 e p95). O estado aparece nos diagnósticos
da integração.

## Instalação/atualização

1. Copie `custom_components/luna_assistant` para `/config/custom_components/`.
2. Reinicie completamente o Home Assistant.
3. A entrada existente é migrada automaticamente para a Prime v1; os serviços
   existentes permanecem no Google.
4. Em **Configurações → Dispositivos e serviços → Luna Assistant Prime**, abra
   ou adicione as entidades AI Task, Conversation, STT e TTS.

## Configurar Azure TTS

1. Reconfigure uma entidade Luna TTS ou adicione outra.
2. Em **Provedor**, selecione **Microsoft Azure Speech**.
3. Envie o formulário uma vez para abrir os campos específicos do Azure.
4. Informe a chave, a região (por exemplo `brazilsouth`) e a voz.
5. Para Google Nest/outro media player, selecione essa entidade no campo
   **Provedor Luna TTS** da Luna Conversation.

Voz padrão: `pt-BR-FranciscaNeural`. O formato padrão é
`riff-24khz-16bit-mono-pcm`.

## Compatibilidade com Luna Satellite

- Serviço `luna_assistant.interrupt_external_audio` preservado.
- Saída Atom continua pelo Assist Pipeline.
- Saída externa continua usando `entity_id` canônico.
- O Satellite é notificado somente quando o player externo termina.
- Barge-in e conversa contínua não foram movidos para o Core.

## Adicionar outro provedor

Consulte [PROVIDER_DEVELOPMENT.md](PROVIDER_DEVELOPMENT.md). Um novo provedor,
como OpenAI, implementa o contrato `LunaProviderAdapter` e é registrado no Hub.
As entidades `ai_task`, `conversation`, `stt` e `tts` permanecem inalteradas.

## Validação

O pacote contém testes estáticos e unitários sem credenciais. Testes físicos no
Home Assistant ainda são obrigatórios porque chamadas reais do Google/Azure e
reprodução no Atom/Nest dependem da instalação do usuário.
