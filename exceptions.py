class ResponseEndpointException(Exception):
    """Ошибка в запросе к конечной точке."""


class MissingTokensError(Exception):
    """Отсутствие обязательных переменных окружения."""
