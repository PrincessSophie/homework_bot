import logging
import os
import sys
import time
from json.decoder import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger()
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s -  %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='homework.log',
)


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        chat_id = TELEGRAM_CHAT_ID
        bot.send_message(chat_id=chat_id, text=message)
        logging.info(f'Бот отправил сообщение "{message}"')
    except telegram.TelegramError as error:
        logger.exception(f'Сообщение {message} не отправлено: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as error:
        logging.error(f'Сбой в работе API сервиса: {error}')
    if response.status_code != 200:
        logging.error(f'HTTPStatus is not OK: {response.status_code}')
        raise exceptions.HTTPStatusNot200(
            f'Эндпоинт {ENDPOINT} недоступен.'
            f'Код ответа API: {response.status_code}'
        )
    try:
        return response.json()
    except JSONDecodeError as error:
        logging.error(f'Ответ от API пришел не в формате JSON: {error}')
        return {}


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не соответствует ожиданиям')
    if 'homeworks' not in response:
        raise KeyError('Нет ключа homeworks в ответе от API')
    homeworks = response['homeworks']
    if not isinstance(response['homeworks'], list):
        raise TypeError('Домашняя работа нет представлена списком.')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    verdict = HOMEWORK_STATUSES[homework['status']]
    homework_name = homework['homework_name']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if PRACTICUM_TOKEN is None:
        logger.error('Переменная PRACTICUM_TOKEN не задана.')
        return False
    if TELEGRAM_TOKEN is None:
        logger.error('Переменная TELEGRAM_TOKEN не задана.')
        return False
    if TELEGRAM_CHAT_ID is None:
        logger.error('Переменная TELEGRAM_CHAT_ID не задана.')
        return False
    else:
        logger.info('Проверка переменных прошла успешна.')
        return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while check_tokens():
        try:
            response = get_api_answer(current_timestamp)
            logger.info('Ответ response получен')
            homework = check_response(response)
            logger.info('response проверен')
            if homework:
                message = parse_status(homework[0])
                logger.info('Статусы получены')
                if message != '':
                    send_message(bot, message)
                    logger.info('Письмо отправлено')
            else:
                logger.info('Статус работы не изменился')
                time.sleep(RETRY_TIME)
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'Проблема с работой. Ошибка {error}')
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
