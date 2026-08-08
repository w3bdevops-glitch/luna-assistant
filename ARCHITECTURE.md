# Arquitetura Luna Assistant Prime v1

```text
Luna Satellite / ESPHome
          ↓
Home Assistant Assist Pipeline
          ↓
Entidades Luna (AI Task, Conversation, STT, TTS)
          ↓
Luna Core
     ├── Provider Hub ── Google Gemini
     │                └─ Azure Speech TTS
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

O Tools Hub é separado do Provider Hub porque ferramentas podem usar mecanismos
ou fornecedores diferentes do modelo de conversa.
