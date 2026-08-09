# Arquitetura Luna Assistant Prime v1.2

```text
Luna Satellite / ESPHome
          ↓
Home Assistant Assist Pipeline
          ↓
Entidades Luna (AI Task, Conversation, STT e TTS)
          ↓
Luna Core
     ├── Provider Hub ── Credential Manager / Usage Meter
     │       ├── Google Gemini
     │       ├── Microsoft Azure Speech
     │       └── Tavily Search
     ├── Tools Hub ───── Search Tool
     ├── Latency Feedback ─ TTS cache / media_player
     └── Metrics
```

## Fronteiras

O Assist Pipeline continua sendo o orquestrador de voz. Luna Core coordena
somente componentes internos da integração. Luna Satellite permanece
proprietário dos estados físicos e de voz do Atom.

## Providers e rotas

Um provider representa uma tecnologia; suas credenciais são recursos internos.
As entidades solicitam capacidades, nunca uma chave. `ProviderRegistry` valida o
contrato do adaptador e `CredentialManager` resolve a rota ordenada, elegibilidade,
saldo, rotação, cooldown, limites e persistência.

| Capacidade | Rota padrão |
|---|---|
| AI Task | Google |
| Conversation | Google |
| STT | Google → Azure |
| TTS | Azure → Google |
| Search | Tavily |
| Image | Google |

O máximo geral de tentativas envolve toda a operação, inclusive a troca de
provider. O máximo do provider pode restringir adicionalmente quantas chaves
daquela tecnologia serão tentadas.

## Consumo e erros

Uma chave elegível é reservada antes da chamada; a unidade medida substitui a
reserva após o retorno. Chamadas e unidades são persistidas de forma assíncrona.
`ProviderError` normaliza categoria, HTTP status e possibilidade de retry.
Somente erros classificados para failover avançam na rota.

## Search e feedback de latência

O Tools Hub anexa Tavily como ferramenta LLM à AI Task ou Conversation quando a
flag geral, o provider, uma credencial e a rota Search estão habilitados. A
resposta retorna dados normalizados para o modelo.

Em paralelo, o Latency Feedback aguarda o limiar configurado e pode reproduzir
uma frase no media player associado ao dispositivo. Os arquivos TTS usam cache
derivado do texto e das opções de voz; pesquisa e áudio não bloqueiam um ao
outro.

## Segurança

Credenciais ficam na configuração protegida do Home Assistant. Diagnósticos
incluem somente sufixos mascarados, metadados operacionais e consumo agregado.
