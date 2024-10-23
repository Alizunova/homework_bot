import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv
from requests.exceptions import RequestException

from telebot import TeleBot

from exceptions import MissingTokensError, ResponseEndpointException

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка доступности переменных окружения."""
    missing_tokens = []
    tokens_dict = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    for key_name, value_token in tokens_dict.items():
        if not value_token:
            missing_tokens.append(key_name)
    if missing_tokens:
        logger.critical(
            f"Отсутствуют обязательные переменные окружения: "
            f"{', '.join(missing_tokens)}."
        )
        raise MissingTokensError(
            "Не заданы необходимые переменные окружения: "
            f"{', '.join(missing_tokens)}. Программа остановлена."
        )
    return len(missing_tokens) == 0


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logger.debug(f"Начало отправки сообщения в Telegram: {message}")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f"Успешно отправлено сообщение: {message}")
        return True
    except (
        telebot.apihelper.ApiException,
        requests.exceptions.RequestException,
    ) as error:
        logger.error(f"Ошибка при отправке сообщения: {error}")
        return False


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту."""
    params_request = {
        "url": ENDPOINT,
        "headers": HEADERS,
        "params": {"from_date": timestamp},
    }
    message = (
        "Выполняется запрос: {url}, {headers}, {params}."
    ).format(**params_request)
    logging.info(message)
    try:
        response = requests.get(**params_request)
    except RequestException as err:
        raise ResponseEndpointException(err)
    if response.status_code != HTTPStatus.OK:
        error_description = f"Ошибка, Код ответа: {response.status_code}"
        raise ResponseEndpointException(error_description)
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(f"Неверный тип данных у элемента {type(response)}")
    check_list_homeworks = response.get("homeworks")
    if check_list_homeworks is None:
        err = "В ответе от API отсутствует ключ homeworks"
        raise ResponseEndpointException(err)
    if not isinstance(check_list_homeworks, list):
        raise TypeError("Неверный тип данных по ключу"
                        f"{type(check_list_homeworks)}")
    if len(check_list_homeworks) == 0:
        logger.debug("В ответе API получен пустой список домашних работ")
    return check_list_homeworks


def parse_status(homework):
    """Статус проверки конкретной домашней работы."""
    if "status" not in homework or "homework_name" not in homework:
        raise KeyError("Отсутствуют ожидаемые ключи в ответе API")
    homework_name = homework["homework_name"]
    status = homework["status"]
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f"Неизвестный статус работы: {status}")
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.info("Вы запустили Бота")
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    timestamp = response.get("current_date", timestamp)
                    last_message = None
            else:
                logger.info("Новых статусов нет.")
        except Exception as error:
            message = f"{error}"
            if last_message != message:
                send_message(bot, message)
                last_message = message
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s - %(lineno)d"
        '- %(message)s',
        handlers=[
            logging.FileHandler("log.txt", encoding="UTF-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )
    main()
