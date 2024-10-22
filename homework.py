
import logging
from telebot import TeleBot
import os
import requests
from requests.exceptions import RequestException
import time
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        logging.info("Отсутствие обязательных переменных окружения!")
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logger.info(f'Начало отправки сообщения в Telegram: {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Успешно отправлено сообщение: {message}')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


class ResponseEndpointException(Exception):
    """Ошибка в запросе к конечной точке."""

    pass


def get_api_answer(current_timestamp):
    """Запрос к единственному эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except RequestException as err:
        raise ResponseEndpointException(err)
    if response.status_code != 200:
        error_description = f"Ошибка, Код ответа: {response.status_code}"
        raise ResponseEndpointException(error_description)
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError("Неверный тип данных у элемента response")
    elif "homeworks" not in response:
        err = "В ответе от API отсутствует ключ homeworks"
        raise ResponseEndpointException(err)
    elif not isinstance(response["homeworks"], list):
        raise TypeError("Неверный тип данных у элемента homeworks")
    return response.get("homeworks")


def parse_status(homework):
    """Статус проверки конкретной домашней работы."""
    if 'status' not in homework or 'homework_name' not in homework:
        raise KeyError('Отсутствуют ожидаемые ключи в ответе API')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.info('Вы запустили Бота')
    if not check_tokens():
        raise logger.critical('Отсутствуют обязательные переменные окружения. '
                              'Программа остановлена!')
    bot = TeleBot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = "Ничего нового не произошло"
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logging.info(message)
        except Exception as error:
            message = f'{error}'
            if last_message != message:
                send_message(bot, message)
                last_message = message
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
