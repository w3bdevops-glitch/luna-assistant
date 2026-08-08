# Luna Assistant Prime v1.1.0

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

## Entregue na Prime v1.1

### Luna Core

Raiz de execução interna que inicializa e conecta o Provider Hub, Tools Hub e
métricas operacionais. Credenciais nunca são incluídas nos diagnósticos.

### Luna Provider Hub

Registro plugável por capacidade. A entidade do Home Assistant solicita uma
capacidade e o Hub seleciona o adaptador configurado.

| Provedor | AI Task | Conversation | STT | TTS |
|---|---:|---:|---:|---:|
| Google Gemini | Sim | Sim | Sim | Sim |
| Microsoft Azure Speech | Não | Não | Sim | Sim |

O Google mantém seleção de modelos e fornece Gemini 3.1 Flash-Lite,
transcrição multimodal e Gemini 3.1 Flash TTS. O Azure usa a API regional Speech
para STT de áudio curto e TTS neural com SSML e áudio WAV PCM validado.

### Lista central de API keys e consumo

Abra **Configurações → Dispositivos e serviços → Luna Assistant Prime →
Configurar**. O menu do Provider Hub permite:

- adicionar, editar, ativar, desativar e remover várias chaves Google e Azure;
- nomear cada chave e definir sua prioridade;
- limitar chamadas diárias e mensais por chave;
- limitar tokens Google, caracteres Azure TTS e segundos Azure STT;
- impor limites globais separados para Google e Azure;
- escolher rotação por prioridade, rodízio ou menor consumo mensal;
- ativar failover entre chaves e, em STT/TTS, entre Google e Azure; definir
  número máximo de tentativas e cooldown.

O consumo é persistido no Home Assistant e reinicia automaticamente nos períodos
diário/mensal. `0` significa ilimitado. Chaves nunca aparecem nos diagnósticos;
somente nome, região, limites, estado, cooldown e consumo agregado.

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
3. A entrada existente é migrada automaticamente para a Prime v1.1; os serviços
   existentes permanecem no Google.
4. Em **Configurações → Dispositivos e serviços → Luna Assistant Prime**, abra
   ou adicione as entidades AI Task, Conversation, STT e TTS.

## Configurar Azure STT e TTS

1. Em **Configurar → Adicionar chave Microsoft Azure**, informe nome, chave,
   região (por exemplo `brazilsouth`), prioridade e limites.
2. Reconfigure ou adicione uma entidade Luna STT ou Luna TTS.
3. Em **Provedor**, selecione **Microsoft Azure Speech**.
4. No TTS, escolha voz e formato; no STT, escolha como tratar palavrões.
5. Para Google Nest/outro media player, selecione a entidade TTS no campo
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
