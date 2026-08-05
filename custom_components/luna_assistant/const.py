# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Constants for the Luna Assistant integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

LOGGER = logging.getLogger(__package__)

DOMAIN = "luna_assistant"
DEFAULT_TITLE = "Luna Assistant"

DEFAULT_CONVERSATION_NAME = "Luna Conversation"
DEFAULT_STT_NAME = "Luna STT"
DEFAULT_TTS_NAME = "Luna TTS"
DEFAULT_AI_TASK_NAME = "Luna AI Task"

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

DEFAULT_TTS_STYLE_PROMPT = (
    "Fale em português do Brasil com voz feminina, alegre, acolhedora e natural. "
    "Use ritmo de conversa, pausas curtas e entonação alto-astral, sem exagerar. "
    "Pronuncie somente a resposta a seguir, sem ler estas instruções:"
)


CONF_RECOMMENDED = "recommended"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "models/gemini-3.1-flash-lite"
RECOMMENDED_STT_MODEL = RECOMMENDED_CHAT_MODEL
RECOMMENDED_TTS_MODEL = "models/gemini-2.5-flash-preview-tts"
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
RECOMMENDED_USE_GOOGLE_SEARCH_TOOL = False
CONF_THINKING_BUDGET = "thinking_budget"
RECOMMENDED_THINKING_BUDGET = -1
CONF_THINKING_LEVEL = "thinking_level"
RECOMMENDED_THINKING_LEVEL = "auto"

TIMEOUT_MILLIS = 10000
FILE_POLLING_INTERVAL_SECONDS = 0.05

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_PROMPT: DEFAULT_CONVERSATION_PROMPT,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_RECOMMENDED: False,
    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
    CONF_TEMPERATURE: 0.7,
}

RECOMMENDED_STT_OPTIONS = {
    CONF_PROMPT: DEFAULT_STT_PROMPT,
    CONF_RECOMMENDED: False,
    CONF_CHAT_MODEL: RECOMMENDED_STT_MODEL,
    CONF_TEMPERATURE: 0.0,
}

RECOMMENDED_TTS_OPTIONS = {
    CONF_PROMPT: DEFAULT_TTS_STYLE_PROMPT,
    CONF_RECOMMENDED: False,
    CONF_CHAT_MODEL: RECOMMENDED_TTS_MODEL,
    CONF_TEMPERATURE: 0.8,
}

RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_RECOMMENDED: True,
}
