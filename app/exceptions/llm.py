class LLMError(Exception):
    """Base error for failures while talking to the LLM provider."""


class LLMUnavailableError(LLMError):
    """The provider could not be reached or rejected the request."""


class LLMTimeoutError(LLMError):
    """The provider did not answer in time."""


class LLMResponseError(LLMError):
    """The LLM answered, but the response could not be parsed or validated."""
