# Luna Assistant Prime v1.0.0

Primeira versão da nova arquitetura plugável.

## Principais mudanças

- Luna Core como raiz interna da integração.
- Provider Hub com contrato, registro e seleção por capacidade.
- Google Gemini para AI Task, Conversation, STT e TTS.
- Microsoft Azure Speech como provedor TTS nativo.
- Tools Hub com pesquisa via Google Search Grounding.
- Métricas internas e erros normalizados nos diagnósticos.
- Migração não destrutiva da série 0.3.x; subentradas existentes continuam Google.
- Seleção da entidade Luna TTS usada em saídas externas.
- Mantidos barge-in, saída Atom, Google Nest e callback ao Luna Satellite.

## Limites desta versão

- Não há rotação automática de várias credenciais.
- Não há failover automático entre Google TTS e Azure TTS.
- Whitelist/blacklist de sites ainda não faz parte do Search Grounding.
- Azure entra apenas como TTS; os outros serviços continuam Google.

Esses recursos podem ser adicionados sobre os contratos atuais sem reescrever
as entidades do Home Assistant.
