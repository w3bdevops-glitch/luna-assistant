# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Constants for the Luna Assistant integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

LOGGER = logging.getLogger(__package__)

DOMAIN = "luna_assistant"
SERVICE_INTERRUPT_EXTERNAL_AUDIO = "interrupt_external_audio"
DEFAULT_TITLE = "Luna Assistant Prime"

DEFAULT_CONVERSATION_NAME = "Luna Conversation"
DEFAULT_STT_NAME = "Luna STT"
DEFAULT_TTS_NAME = "Luna TTS"
DEFAULT_AI_TASK_NAME = "Luna AI Task"

# Luna Provider Hub
CONF_PROVIDER = "provider"
PROVIDER_GOOGLE = "google"
PROVIDER_AZURE = "azure"
DEFAULT_PROVIDER = PROVIDER_GOOGLE
# Central Provider Hub credential and consumption controls.
CONF_CREDENTIALS = "credentials"
CONF_AUTO_FAILOVER = "auto_failover"
CONF_FAILOVER_ATTEMPTS = "failover_attempts"
CONF_FAILOVER_COOLDOWN = "failover_cooldown_seconds"
CONF_ROTATION_STRATEGY = "rotation_strategy"
CONF_PROVIDER_LIMITS = "provider_limits"
DEFAULT_FAILOVER_ATTEMPTS = 3
DEFAULT_FAILOVER_COOLDOWN = 300
DEFAULT_ROTATION_STRATEGY = "priority"
ROTATION_STRATEGIES = ("priority", "round_robin", "least_used")

# Credential editor fields used only by the integration options flow.
CONF_CREDENTIAL_ID = "credential_id"
CONF_CREDENTIAL_NAME = "credential_name"
CONF_CREDENTIAL_ACTION = "credential_action"
CONF_ENABLED = "enabled"
CONF_PRIORITY = "priority"
CONF_DAILY_REQUEST_LIMIT = "daily_request_limit"
CONF_MONTHLY_REQUEST_LIMIT = "monthly_request_limit"
CONF_MONTHLY_TOKEN_LIMIT = "monthly_token_limit"
CONF_MONTHLY_TTS_CHARACTER_LIMIT = "monthly_tts_character_limit"
CONF_MONTHLY_STT_SECONDS_LIMIT = "monthly_stt_seconds_limit"
CONF_AZURE_SPEECH_KEY = "azure_speech_key"
CONF_AZURE_REGION = "azure_region"
CONF_AZURE_VOICE = "azure_voice"
CONF_AZURE_OUTPUT_FORMAT = "azure_output_format"
CONF_AZURE_STT_PROFANITY = "azure_stt_profanity"
DEFAULT_AZURE_REGION = "brazilsouth"
DEFAULT_AZURE_VOICE = "pt-BR-FranciscaNeural"
DEFAULT_AZURE_OUTPUT_FORMAT = "riff-24khz-16bit-mono-pcm"
DEFAULT_AZURE_STT_PROFANITY = "raw"
AZURE_PT_BR_VOICES = (
    "pt-BR-FranciscaNeural",
    "pt-BR-ThalitaMultilingualNeural",
    "pt-BR-ThalitaNeural",
    "pt-BR-BrendaNeural",
    "pt-BR-GiovannaNeural",
    "pt-BR-ManuelaNeural",
    "pt-BR-YaraNeural",
    "pt-BR-AntonioNeural",
    "pt-BR-DonatoNeural",
    "pt-BR-FabioNeural",
)

DEFAULT_STT_PROMPT = (
    "Transcreva fielmente o áudio em português do Brasil. "
    "Corrija apenas hesitações e pontuação, sem inventar palavras."
)

DEFAULT_CONVERSATION_PROMPT = (
    "Você é Luna, uma assistente residencial alegre, natural e objetiva. "
    "Responda em português do Brasil, normalmente em até duas frases. "
    "Quando uma ação da casa for solicitada, execute-a sem explicações longas. "
    "Não diga que executou uma ação antes de receber confirmação da ferramenta."
)

RELIABILITY_PROMPT = (
    "REGRAS OBRIGATÓRIAS DE CONFIABILIDADE: Nunca invente, estime ou complete "
    "fatos, nomes, números, datas, ingredientes, etapas, resultados ou fontes. "
    "Não apresente suposições como fatos e nunca afirme que pesquisou quando não "
    "pesquisou. Para qualquer informação atual, específica, verificável ou sobre "
    "a qual não tenha segurança suficiente — incluindo notícias, esportes, clima, "
    "preços, horários, pessoas, tecnologia, saúde, receitas e acontecimentos "
    "recentes — use a pesquisa na internet antes de responder, quando a ferramenta "
    "estiver disponível. Se não souber ou não houver confirmação suficiente, diga "
    "claramente: 'Não sei responder com segurança. Preciso pesquisar ou me "
    "aprofundar mais.' Se a pesquisa falhar ou for inconclusiva, diga: 'Não consegui "
    "confirmar essa informação agora.' É sempre melhor admitir que não sabe do que "
    "fornecer uma resposta possivelmente incorreta. Diferencie explicitamente fatos "
    "confirmados, hipóteses, sugestões e criações. Ao ser corrigida, não improvise "
    "outra resposta: pesquise novamente ou admita que não conseguiu confirmar."
)

DEFAULT_TTS_STYLE_PROMPT = (
    "Fale em português do Brasil com voz feminina, alegre, acolhedora e natural. "
    "Use ritmo de conversa, pausas curtas e entonação alto-astral, sem exagerar. "
    "Pronuncie somente a resposta a seguir, sem ler estas instruções:"
)


CONF_RECOMMENDED = "recommended"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "models/gemini-3.1-flash-lite"
RECOMMENDED_STT_MODEL = RECOMMENDED_CHAT_MODEL
RECOMMENDED_TTS_MODEL = "models/gemini-3.1-flash-tts-preview"
RECOMMENDED_IMAGE_MODEL = "models/gemini-2.5-flash-image"
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_TOP_P = "top_p"
RECOMMENDED_TOP_P = 0.95
CONF_TOP_K = "top_k"
RECOMMENDED_TOP_K = 64
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 3000
# Input 5000, output 19400 = 0.05 USD
RECOMMENDED_AI_TASK_MAX_TOKENS = 19400
CONF_HARASSMENT_BLOCK_THRESHOLD = "harassment_block_threshold"
CONF_HATE_BLOCK_THRESHOLD = "hate_block_threshold"
CONF_SEXUAL_BLOCK_THRESHOLD = "sexual_block_threshold"
CONF_DANGEROUS_BLOCK_THRESHOLD = "dangerous_block_threshold"
RECOMMENDED_HARM_BLOCK_THRESHOLD = "BLOCK_MEDIUM_AND_ABOVE"
CONF_USE_GOOGLE_SEARCH_TOOL = "enable_google_search_tool"
RECOMMENDED_USE_GOOGLE_SEARCH_TOOL = True
CONF_THINKING_BUDGET = "thinking_budget"
RECOMMENDED_THINKING_BUDGET = -1
CONF_THINKING_LEVEL = "thinking_level"
RECOMMENDED_THINKING_LEVEL = "auto"


CONF_PERSONALITY = "personality"
CONF_RESPONSE_LENGTH = "response_length"
CONF_LATENCY_PROFILE = "latency_profile"
CONF_VOICE_MOOD = "voice_mood"
CONF_SPEAKING_PACE = "speaking_pace"

# Voice response destination. This belongs to Luna Assistant/Home Assistant,
# never to the ESPHome satellite firmware.
CONF_AUDIO_OUTPUT = "audio_output"
CONF_OUTPUT_MEDIA_PLAYER = "output_media_player"
CONF_OUTPUT_TTS_ENTITY = "output_tts_entity"

AUDIO_OUTPUT_ATOM = "atom"
AUDIO_OUTPUT_GOOGLE_NEST = "google_nest"
AUDIO_OUTPUT_MEDIA_PLAYER = "media_player"
DEFAULT_AUDIO_OUTPUT = AUDIO_OUTPUT_ATOM

DEFAULT_PERSONALITY = "playful"
DEFAULT_RESPONSE_LENGTH = "short"
DEFAULT_LATENCY_PROFILE = "fast"
DEFAULT_VOICE_MOOD = "cheerful"
DEFAULT_SPEAKING_PACE = "natural"

# Runtime behavior for the latency profile selector.
LATENCY_PROFILE_MAX_TOKENS = {
    "fast": 256,
    "balanced": 1024,
    "quality": RECOMMENDED_MAX_TOKENS,
}
LATENCY_PROFILE_TOOL_ITERATIONS = {
    "fast": 4,
    "balanced": 8,
    "quality": 10,
}
LATENCY_PROFILE_THINKING_LEVEL = {
    "fast": "minimal",
    "balanced": "low",
    "quality": "auto",
}

PERSONALITY_PROMPTS = {
    "playful": ("Seja leve, brincalhona e espontânea, com humor sutil e sem exageros."),
    "warm": ("Seja acolhedora, calma e próxima, mantendo respostas claras e naturais."),
    "direct": ("Seja direta, prática e objetiva, sem introduções desnecessárias."),
    "teacher": (
        "Explique com clareza, exemplos simples e tom paciente, sem infantilizar."
    ),
    "technical": (
        "Seja técnica e precisa, usando detalhes quando forem realmente úteis."
    ),
}

RESPONSE_LENGTH_PROMPTS = {
    "very_short": "Responda em uma frase curta sempre que possível.",
    "short": "Responda normalmente em até duas frases.",
    "balanced": "Responda de forma equilibrada, com apenas os detalhes necessários.",
    "detailed": "Dê uma resposta mais completa quando o assunto exigir.",
}

LATENCY_PROFILE_PROMPTS = {
    "fast": (
        "Priorize velocidade e respostas curtas. Evite raciocínios longos "
        "quando uma resposta simples for suficiente."
    ),
    "balanced": (
        "Equilibre velocidade e qualidade, aprofundando apenas quando necessário."
    ),
    "quality": (
        "Priorize qualidade e precisão, mesmo que a resposta leve um pouco mais."
    ),
}

VOICE_MOOD_PROMPTS = {
    "cheerful": "alegre, luminosa e alto-astral",
    "warm": "acolhedora, suave e simpática",
    "calm": "calma, serena e confortável",
    "enthusiastic": "entusiasmada, viva e positiva",
    "professional": "confiante, clara e profissional",
}

SPEAKING_PACE_PROMPTS = {
    "slow": "Fale um pouco mais devagar, com pausas naturais.",
    "natural": "Use ritmo natural de conversa, com pausas curtas.",
    "fast": "Fale de forma ágil, mas sem perder clareza.",
}

TIMEOUT_MILLIS = 10000
FILE_POLLING_INTERVAL_SECONDS = 0.05

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_PROVIDER: PROVIDER_GOOGLE,
    CONF_PROMPT: DEFAULT_CONVERSATION_PROMPT,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_RECOMMENDED: False,
    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
    CONF_TEMPERATURE: 0.7,
    CONF_PERSONALITY: DEFAULT_PERSONALITY,
    CONF_RESPONSE_LENGTH: DEFAULT_RESPONSE_LENGTH,
    CONF_LATENCY_PROFILE: DEFAULT_LATENCY_PROFILE,
    CONF_AUDIO_OUTPUT: DEFAULT_AUDIO_OUTPUT,
    CONF_USE_GOOGLE_SEARCH_TOOL: RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
}

RECOMMENDED_STT_OPTIONS = {
    CONF_PROVIDER: PROVIDER_GOOGLE,
    CONF_PROMPT: DEFAULT_STT_PROMPT,
    CONF_RECOMMENDED: False,
    CONF_CHAT_MODEL: RECOMMENDED_STT_MODEL,
    CONF_TEMPERATURE: 0.0,
}

RECOMMENDED_TTS_OPTIONS = {
    CONF_PROVIDER: PROVIDER_GOOGLE,
    CONF_PROMPT: DEFAULT_TTS_STYLE_PROMPT,
    CONF_RECOMMENDED: False,
    CONF_CHAT_MODEL: RECOMMENDED_TTS_MODEL,
    CONF_TEMPERATURE: 0.8,
    CONF_VOICE_MOOD: DEFAULT_VOICE_MOOD,
    CONF_SPEAKING_PACE: DEFAULT_SPEAKING_PACE,
}

RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_PROVIDER: PROVIDER_GOOGLE,
    CONF_RECOMMENDED: True,
}
