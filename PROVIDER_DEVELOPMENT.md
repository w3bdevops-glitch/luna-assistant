# Como adicionar um provider

Um provider representa uma tecnologia, não uma conta ou API key.

1. Adicione o identificador, nome, capacidades e rota padrão em `const.py`.
2. Crie `custom_components/luna_assistant/provider_hub/<provider>.py`.
3. Implemente `LunaProviderAdapter` e declare somente as capacidades reais.
4. Obtenha credenciais exclusivamente por `CredentialManager.async_acquire()`.
5. Após sucesso, chame `async_complete()` com a unidade medida; após falha,
   normalize em `ProviderError` e chame `async_fail()`.
6. Registre uma única instância tecnológica em `LunaProviderHub`.
7. Adicione o formulário do provider e de suas credenciais ao Options Flow.
8. Acrescente traduções, documentação, testes do adaptador, rotação, limites,
   failover e migração.

Exemplo de capacidades:

```python
capabilities = frozenset(
    {
        ProviderCapability.AI_TASK,
        ProviderCapability.CONVERSATION,
        ProviderCapability.STT,
        ProviderCapability.TTS,
    }
)
```

Implemente apenas os contratos correspondentes, como
`async_handle_chat_log`, `async_transcribe`, `async_synthesize` ou
`async_search`.

## Regras de dependência

- Código do fornecedor fica em `provider_hub/<provider>.py`.
- Entidades não leem segredos e não importam SDKs de providers.
- Rotas usam identificadores tecnológicos e nunca IDs de credenciais.
- Ferramentas do modelo ficam no Tools Hub, mesmo quando consomem um provider.
- Luna Core, Assist Pipeline e Luna Satellite não devem ganhar lógica específica
  do novo fornecedor.
