import logging
import os
import sys
import time
 
import requests
import telegram
from dotenv import load_dotenv
 
import exceptions
 
load_dotenv()
 
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
 
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
RETRY_TIME = 600 
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
 
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
 
 
def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
        logging.info(f'Бот отправил сообщение "{message}"')
    except telegram.TelegramError as error:
        logging.error(f'Сообщение {message} не отправлено: {error}')
 
 
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
        raise ConnectionError(f'Ошибка доступа {error}. '
                              f'Проверить API: {ENDPOINT}, '
                              f'Токен авторизации: {HEADERS}, '
                              f'Запрос с момента времени: {params}')
    response_json = response.json()
    for key in ['code', 'error']:
        if key in response_json:
            raise exceptions.ResponseError(
                f'{key}',
                f'{response_json[key]}',
                f'{ENDPOINT}',
                f'{HEADERS}',
                f'{params}'
            )
    if response.status_code != 200:
        raise exceptions.StatusCodeError(
            f'Ошибка ответа сервера. Проверить API: {ENDPOINT}, '
            f'Токен авторизации: {HEADERS}, '
            f'Запрос с момента времени: {params},'
            f'Код возврата {response.status_code}'
        )
    return response_json
 
 
def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('В ответе от API нет корректных данных', type(response))
    if 'homeworks' not in response:
        raise KeyError('Нет ключа homeworks в ответе от API')
    homeworks = response['homeworks']
    if not isinstance(response['homeworks'], list):
        raise TypeError('Домашняя работа ожидается списком', type(response['homeworks']))
    return homeworks
 
 
def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_STATUSES:
        raise ValueError(f'Неизвестный статус домашней работы {status}')
    verdict = HOMEWORK_STATUSES[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'
 
 
def check_tokens():
    """Проверяет доступность переменных окружения."""
    invalid_tokens = [name for name in TOKENS if not globals()[name]]
    if invalid_tokens:
        for name in invalid_tokens:
            logging.error('Отсутствует токен {}'.format(name))
        return False
    return True
 
 
def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Проверьте значение токенов')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.info("Новые статусы отсутствуют.")
                time.sleep(RETRY_TIME)
            else:
                send_message(bot, parse_status(homeworks[0]))
            current_timestamp = response.get(
                'current_date', current_timestamp
            )
        except Exception as error:
            message = f'Сбой в работе телеграмм-бота: {error}'
            logging.error(message)
            if last_message != message:
                send_message(bot, message)
                last_message = message
 
 
if __name__ == '__main__':
    LOG_FILE = __file__ + '.log'
    logging.basicConfig(
        handlers=[logging.FileHandler(LOG_FILE),
                  logging.StreamHandler(sys.stdout)],
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    main()
 