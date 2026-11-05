class LLMError(Exception):
    """Base error for failures while talking to the LLM provider."""


class LLMResponseError(LLMError):
    """The LLM answered, but the response could not be parsed or validated."""
