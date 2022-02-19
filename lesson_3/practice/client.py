import sys
import json
import argparse
import logging
import socket as sck
import threading
import logs.config_client_log
from errors import *
from common.variables import *
from common.utils import *
import time
from decos import log
from metaclasses import ClientMaker
# Инициализация клиентского логера
CLIENT_LOGGER = logging.getLogger('client')

# Класс формировки и отправки сообщения на сервер и взаимодействия с пользователем.
class ClientSender(threading.Thread, metaclass=ClientMaker):
    def __init__(self, account_name, sock):
        self.account_name = account_name
        self.sock = sock
        super().__init__()

    # Функция создает словарь с сообщением о выходе
    def create_exit_message(self):
        return {
            ACTION: EXIT,
            TIME: time.time(),
            ACCOUNT_NAME: self.account_name
        }

    def create_message(self):
        """
        Функция запрашивает текст сообщения и возвращает его.
        Так же завершает работу при вводе подобной комманды
        """
        to_user = input('Введите получателя сообщения: ')
        message = input('Введите сообщение для отправки: ')
        message_dict = {
            ACTION: MESSAGE,
            SENDER: self.account_name,
            DESTINATION: to_user,
            TIME: time.time(),
            MESSAGE_TEXT: message
        }
        CLIENT_LOGGER.debug(f'Сформирован словарь сообщения: {message_dict}')
        try:
            send_message(self.sock, message_dict)
            CLIENT_LOGGER.info(f'Отправлено сообщение для пользователя {to_user}')
        except:
            CLIENT_LOGGER.critical('Потеряно соединение с сервером.')
            exit(1)

    def run(self):
        """
        Функция взаимодействия с пользователем. Запрашивает команы, отправляет сообщения.
        """
        self.print_help()
        while True:
            command = input('Введите команду: ')
            if command == 'message':
                self.create_message()
            elif command == 'help':
                self.print_help()
            elif command == 'exit':
                try:
                    send_message(self.sock, self.create_exit_message())
                except:
                    pass
                print('Завершение соединения.')
                CLIENT_LOGGER.info('Завершение работы по команде ползователя.')
                # Задержка, чтобы успело уйти сообщение о выходе.
                time.sleep(0.5)
                break
            else:
                print('Команда не распознана, попробуйте снова. help - вывести поддерживаемые команды.')

    def print_help(self):
        """Справка по пользованию"""
        print('Поддерживаемые команды:')
        print('message - отправтиь сообщение. Адрес и текст будут запрошены отдельно.')
        print('help - вывести подсказки по командам.')
        print('exit - ыход из программы.')

# Класс-приемник сообщений с сервера. Принимает сообщения, выводит в консоль.
class ClientReader(threading.Thread, metaclass=ClientMaker):
    def __init__(self, account_name, sock):
        self.account_name = account_name
        self.sock = sock
        super().__init__()

    # Основной цикл приемника сообщений. Принимает сообщения, вывоит в консоль. Завершается при потере соединения.
    def run(self):
        while True:
            try:
                message = get_message(self.sock)
                if ACTION in message and message[ACTION] == MESSAGE and \
                        SENDER in message and DESTINATION in message \
                        and MESSAGE_TEXT in message and message[DESTINATION] == self.account_name:
                    print(f'Получено сообщение от пользователя '
                          f'{message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                    CLIENT_LOGGER.info(f'Получено сообщение от пользователя '
                                       f'{message[SENDER]}:{message[MESSAGE_TEXT]}')
                else:
                    CLIENT_LOGGER.error(f'Получено некорректное сообщение с сервера: {message}')
            except IncorrectDataReceivedError:
                CLIENT_LOGGER.error(f'Не удалось декодировать сообщение.')
            except (OSError, ConnectionError, ConnectionAbortedError,
                    ConnectionResetError, json.JSONDecodeError):
                CLIENT_LOGGER.critical(f'Потеряно соединение с сервером.')
                break

@log
def create_presence(account_name):
    """
    Функция генерирует запрос о присутствии клиента
    :param account_name:
    :return:
    """
    out = {
        ACTION: PRESENCE,
        TIME: time.time(),
        USER: {
            ACCOUNT_NAME: account_name
        }
    }
    CLIENT_LOGGER.debug(f'Сформированно {PRESENCE} сообщение для пользователя {account_name}.')
    return out

@log
def process_ans(message):
    """
    Функция разбирает ответ сервера
    :param message:
    :return:
    """
    CLIENT_LOGGER.debug(f'Разбор сообщения от сервера: {message}')
    if RESPONSE in message:
        if message[RESPONSE] == 200:
            return '200 : OK'
        elif message[RESPONSE] == 400:
            raise ServerError(f'400 : {message[ERROR]}')
    raise ReqFieldMissongError(RESPONSE)

@log
def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('addr', default=DEFAULT_IP_ADRESS, nargs='?')
    parser.add_argument('port', default=DEFAULT_PORT, type=int, nargs='?')
    parser.add_argument('-m', '--name', default=None, nargs='?')
    namespace = parser.parse_args(sys.argv[1:])
    server_address = namespace.addr
    server_port = namespace.port
    client_name = namespace.name


    if not 1023 < server_port < 65536:
        CLIENT_LOGGER.critical(f'Попытка запуска клиента с неподходящим номером порта: {server_port}. '
                               f'Допустимы адреса с 1024 до 65535. Клиента завершается.')
        sys.exit(1)

    return server_address, server_port, client_name


def main():
    """
    Загружаем параметры коммандной строки.
    :return:
    """
    server_address, server_port, client_name = create_arg_parser()
    """Сообщаем о запуске"""
    print(f'Консольный мессенджер. Клиентский модуль. Имя пользователя: {client_name}')

    # Если имя пользователя не было задано, необходимо запросить пользователя.
    if not client_name:
        client_name = input('Введите имя пользователя: ')

    CLIENT_LOGGER.info(f'Запущен клиент с параметрами: '
                       f'адрес сервера: {server_address}, порт: {server_port},'
                       f'режим работы: {client_name}')

    # инициализация сокета и сообщение серверу о появлении
    try:
        transport = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
        transport.connect((server_address, server_port))
        send_message(transport, create_presence(client_name))
        answer = process_ans(get_message(transport))
        CLIENT_LOGGER.info(f'Установлено соединение с сервером. Принят ответ от сервера {answer}')
        print(f'Установлено соединение с сервером.')
    except json.JSONDecodeError:
        CLIENT_LOGGER.error(f'Не удалось декодировать полученную Json строку.')
        exit(1)
    except ServerError as error:
        CLIENT_LOGGER.error(f'При установке соединения сервер вернул ошибку: {error.text}')
        exit(1)
    except ReqFieldMissongError as missing_error:
        CLIENT_LOGGER.error(f'В ответе сервера отстутствует необходимое поле {missing_error.missing_field}')
        exit(1)
    except (ConnectionRefusedError, ConnectionError):
        CLIENT_LOGGER.critical(f'Не удалось подключиться к серверу {server_address}:{server_port}, '
                               f'конечный компьютер отверг запрос на подключение.')
        exit(1)
    else:
        # Если соединение с сервером установлено корректно,
        # запускаем клиентский процесс приема сообщений
        receiver = ClientReader(client_name, transport)
        receiver.daemon = True
        receiver.start()

        # Затем запускаем отправку сообщений и взаимодействие с пользователем.
        sender = ClientSender(client_name, transport)
        sender.daemon = True
        sender.start()
        CLIENT_LOGGER.debug('Запущены процессы')
        # Watchdog основной цикл, если один из потоков завершён,
        # то значит или потеряно соединение или пользователь
        # ввёл exit. Поскольку все события обработываются в потоках,
        # достаточно просто завершить цикл.
        while True:
            time.sleep(1)
            if receiver.is_alive() and sender.is_alive():
                continue
            break


if __name__ == '__main__':
    main()
    input('')