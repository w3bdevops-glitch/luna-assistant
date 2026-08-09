# Luna Assistant Prime v1.2.0

Integração personalizada para o Home Assistant 2026.7 que fornece IA ao
Assist Pipeline sem substituir sua orquestração nativa.

## O que há de novo

- Providers são tecnologias únicas: **Google Gemini**, **Microsoft Azure
  Speech** e **Tavily Search**. As API keys pertencem ao provider e não criam
  providers duplicados.
- Rotas centrais e ordenadas por capacidade: AI Task, Conversation, STT, TTS,
  Search e Image.
- Quantidade livre de credenciais em cada provider, com rotação pela maior
  estimativa de saldo ou por round-robin.
- Failover entre chaves e providers compatíveis, cooldown individual e limite
  total de tentativas por operação.
- Limites locais diários/mensais e medição persistente de chamadas e unidades.
- Tavily como ferramenta nativa de pesquisa para AI Task e Conversation.
- Chave geral **Habilitar pesquisa na internet**, ligada por padrão.
- Cinco frases de feedback para mascarar a latência da pesquisa, com geração
  antecipada pela rota TTS, cache, reprodução aleatória e pré-visualização.
- Migração automática das configurações e credenciais das versões anteriores.

## Arquitetura preservada

- **Luna Satellite / ESPHome** continua responsável por hardware, wake word,
  botões, I²S e estados físicos do Atom.
- **Home Assistant Assist** continua orquestrando `STT → Conversation → TTS`.
- **Luna Assistant Prime** fornece entidades, personalidade, ferramentas,
  providers, rotas, métricas e áudio externo.

Luna Core não assume o microfone, a sessão do Satellite nem o barramento I²S.

## Matriz de providers

| Provider | AI Task | Conversation | STT | TTS | Search | Image |
|---|---:|---:|---:|---:|---:|---:|
| Google Gemini | Sim | Sim | Sim | Sim | Não | Sim |
| Microsoft Azure Speech | Não | Não | Sim | Sim | Não | Não |
| Tavily | Não | Não | Não | Não | Sim | Não |

Rotas padrão: Google para AI Task, Conversation e Image; Google com fallback
Azure para STT; Azure com fallback Google para TTS; Tavily para Search.

## Configuração geral

Abra **Configurações → Dispositivos e serviços → Luna Assistant Prime →
Configurar**. O menu permite:

1. Definir a política geral de pesquisa e failover.
2. Configurar providers e qualquer quantidade de credenciais.
3. Ordenar providers em cada rota de capacidade.
4. Editar, gerar e pré-visualizar as frases de latência.
5. Salvar toda a configuração central.

### Pesquisa na internet

A opção geral **Habilitar pesquisa na internet** é a chave mestra. Quando
desligada, a ferramenta não é oferecida ao modelo, mesmo que Tavily esteja
configurado. Quando ligada, Tavily precisa estar habilitado, ter ao menos uma
chave válida e fazer parte da rota Search.

O controle antigo por entidade Conversation é migrado: se havia valores
explícitos, a opção geral fica ligada quando pelo menos uma conversa permitia
pesquisa; sem configuração anterior, o padrão é ligado.

### Providers, credenciais e consumo

Cada provider possui estado, capacidades, estratégia de rotação, cooldown,
limites globais e uma lista ilimitada de credenciais. Cada credencial pode ser
nomeada, priorizada, ativada ou desativada. Credenciais Azure incluem sua região.

O seletor por maior saldo considera os limites herdados e evita chaves em
cooldown ou esgotadas. Empates são distribuídos. O round-robin força rodízio.
`0` em limites ou tentativas significa ilimitado/tentar todas as opções
elegíveis. Os limites são proteções locais; o portal de cada provider continua
sendo a fonte oficial de cota e faturamento.

O consumo é persistido fora do caminho crítico. Diagnósticos mostram apenas a
identificação mascarada, consumo, saldo estimado, rota, cooldown e último erro.

### Frases durante a pesquisa

Por padrão, a Luna usa cinco frases curtas. A geração ocorre em segundo plano
pela rota TTS configurada e os arquivos são reutilizados enquanto texto, voz e
configuração permanecerem iguais. Durante uma pesquisa lenta, uma frase é
escolhida sem repetição imediata e reproduzida no media player associado ao
dispositivo, quando disponível. A interface permite editar, gerar novamente e
pré-visualizar cada frase.

## Instalação/atualização

1. Copie `custom_components/luna_assistant` para
   `/config/custom_components/luna_assistant`.
2. Reinicie completamente o Home Assistant.
3. Abra a configuração da Luna, cadastre a chave Tavily se quiser pesquisa e
   revise as rotas.
4. Salve. As entradas antigas são migradas automaticamente para o esquema 2:10.

Para HACS, publique o conteúdo deste pacote no repositório, crie a tag
`v1.2.0` e anexe o ZIP da release.

## Compatibilidade com Luna Satellite

- Serviço `luna_assistant.interrupt_external_audio` preservado.
- Saída Atom continua pelo Assist Pipeline.
- Saída externa continua usando o `entity_id` canônico.
- O Satellite é notificado somente quando o player externo termina.
- Barge-in e conversa contínua permanecem fora do Luna Core.

## Validação

O pacote inclui verificações estáticas e testes executáveis sem credenciais.
Chamadas reais Google/Azure/Tavily e reprodução física no Atom/Nest ainda devem
ser validadas na instalação antes da promoção para estável.

Detalhes: [ARCHITECTURE.md](ARCHITECTURE.md),
[PROVIDER_DEVELOPMENT.md](PROVIDER_DEVELOPMENT.md) e
[RELEASE_NOTES.md](RELEASE_NOTES.md).
