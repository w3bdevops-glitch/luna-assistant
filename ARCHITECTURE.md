# Arquitetura Luna Assistant Prime v1.1

```text
Luna Satellite / ESPHome
          ↓
Home Assistant Assist Pipeline
          ↓
Entidades Luna (AI Task, Conversation, STT, TTS)
          ↓
Luna Core
     ├── Provider Hub ── Credential Manager / Consumption
     │                ├─ Google Gemini
     │                └─ Azure Speech STT/TTS
     ├── Tools Hub ───── Google Search Grounding
     └── Metrics
```

## Limites

O Assist Pipeline continua sendo o orquestrador de voz. Luna Core coordena
somente componentes internos da integração. Luna Satellite continua proprietário
dos estados físicos e de voz do Atom.

## Contratos

`LunaProviderAdapter` define operações comuns. `ProviderRegistry` registra
adaptadores e resolve um provedor por `ProviderCapability`. O Hub é a única
camada consultada pelas entidades.

`ProviderError` normaliza categoria, código HTTP e possibilidade de repetição.
`AudioResult` normaliza WAV, taxa, canais, profundidade e voz.

`CredentialManager` fica abaixo do Hub e acima dos adaptadores. Ele reserva uma
credencial elegível antes da chamada, aplica limites por período, seleciona a
próxima chave, persiste o consumo e impõe cooldown. Os adaptadores reportam a
unidade real de cada serviço: tokens, caracteres ou segundos de áudio.

O Hub tenta primeiro todas as credenciais elegíveis do provedor selecionado.
Com failover automático, STT e TTS podem continuar no outro provedor registrado;
Conversation, AI Task e imagem não trocam de provedor porque só o Google oferece
essas capacidades nesta versão.

O Tools Hub é separado do Provider Hub porque ferramentas podem usar mecanismos
ou fornecedores diferentes do modelo de conversa.
