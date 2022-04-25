import logging
import os
import sys
import time
from http import HTTPStatus

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


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        chat_id = TELEGRAM_CHAT_ID
        bot.send_message(chat_id=chat_id, text=message)
        logging.info('Успешная отправка сообщения')
    except exceptions.SendMessageException as error:
        logging.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception:
        message = 'API ведет себя незапланированно'
        raise exceptions.APIAnswerError(message)
    if response.status_code != HTTPStatus.OK:
        message = 'Эндпоинт не отвечает'
        raise Exception(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не соответсвует ожиданиям')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ответ API не соответствует ожиданиям')
    homework = response.get('homeworks')
    return homework


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if not (('homework_name' in homework) and ('status' in homework)):
        raise KeyError('Не обнаружены требуемые ключи в homework')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    message = 'status invalid'
    if homework_status not in HOMEWORK_STATUSES:
        logger.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}".{verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    statuses = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if None in statuses:
        for status in statuses:
            if status is None:
                logger.critical(
                    f'Отсутствует обязательная переменная окружения: {status}'
                )
        return False
    return True


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(TELEGRAM_CHAT_ID, 'Бот запущен')
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            try:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            except Exception:
                message = 'Ошибка во взаимодействии с Telegram'
                logger.error(message)
            time.sleep(RETRY_TIME)
        else:
            message = 'Удачная отправка сообщения в Телеграм'
            logger.info(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
