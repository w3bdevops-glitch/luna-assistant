# Luna Assistant Prime v1.1.0

Segunda versão da arquitetura Prime, agora com credenciais múltiplas, controle
de consumo e Azure Speech-to-Text.

## Principais mudanças

- Lista central de API keys para Google Gemini e Microsoft Azure Speech.
- Interface para adicionar, editar, ativar, priorizar e remover credenciais.
- Limites por chave e por provedor para chamadas diárias/mensais.
- Controle de tokens Google, caracteres Azure TTS e segundos Azure STT.
- Rotação por prioridade, round-robin ou menor consumo mensal.
- Failover automático entre chaves e, em STT/TTS, entre Google e Azure, com
  tentativas e cooldown.
- Contadores persistentes e diagnósticos sem exposição de segredos.
- Azure STT para áudio curto do Assist Pipeline em WAV/PCM ou OGG/Opus.
- Migração não destrutiva das chaves Google/Azure já configuradas.

## Segurança e limites

- API keys ficam somente na configuração protegida do Home Assistant.
- `0` em um limite significa ilimitado.
- Os limites da Luna são preventivos locais; os portais Google/Azure continuam
  sendo a fonte oficial de faturamento e cota.
- O failover entre provedores aplica-se somente a STT/TTS, capacidades que ambos
  oferecem. Conversation, AI Task e imagens continuam no Google.
- Whitelist/blacklist de sites ainda não faz parte do Search Grounding.

## Status

Versão destinada a testes reais antes de promoção para estável. É necessário
validar com credenciais reais, Home Assistant, Atom e, se usado, Google Nest.
