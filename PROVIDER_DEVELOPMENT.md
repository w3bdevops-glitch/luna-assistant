# Como adicionar um provedor

Exemplo futuro: OpenAI.

1. Crie `custom_components/luna_assistant/provider_hub/openai.py`.
2. Implemente `LunaProviderAdapter`.
3. Declare apenas as capacidades reais, por exemplo:

   ```python
   capabilities = frozenset({
       ProviderCapability.AI_TASK,
       ProviderCapability.CONVERSATION,
       ProviderCapability.STT,
       ProviderCapability.TTS,
   })
   ```

4. Implemente somente os métodos correspondentes:
   `async_handle_chat_log`, `async_transcribe` e/ou `async_synthesize`.
5. Registre uma instância em `LunaProviderHub.__init__`.
6. Adicione o formulário de credenciais do provedor no Options Flow e declare
   a unidade de consumo de cada capacidade. Use `CredentialManager`; não leia
   chaves diretamente da entidade.
7. A lista de provedores
   exibida para cada serviço vem automaticamente de `available_providers()`.
8. Acrescente traduções e testes do adaptador, rotação e failover.

Não altere o Luna Satellite, o Assist Pipeline ou as entidades de plataforma.
As respostas devem usar `ProviderError` e áudio deve usar `AudioResult`.

## Regra de dependência

Código específico de fornecedor fica dentro de `provider_hub/<provider>.py`.
Luna Core e as entidades não devem importar SDKs de fornecedores novos.
