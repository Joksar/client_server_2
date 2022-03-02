import sys
import select
import socket as sck
import time
import argparse
import json
import logging
import logs.config_server_log
from errors import IncorrectDataReceivedError
import threading
from common.variables import *
from common.utils import *
from decos import log
from descipts import Port
from metaclasses import ServerMaker
from dbase_creator.server_db_decl import ServerDB
# Инициализация логирования сервера.
SERVER_LOGGER = logging.getLogger('server')

@log
def create_arg_parser():
    """Парсер аргументов командной строки"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', default=DEFAULT_PORT, type=int, nargs='?')
    parser.add_argument('-a', default='', nargs='?')
    namespace = parser.parse_args(sys.argv[1:])
    listen_address = namespace.a
    listen_port = namespace.p
    return listen_address, listen_port

# Основной класс сервера
class Server(threading.Thread, metaclass=ServerMaker):
    port = Port()

    def __init__(self, listen_address, listen_port, database):
        # Параметры подключения
        self.addr = listen_address
        self.port = listen_port
        # База данных сервера
        self.database = database
        # Список клиентов, очередь сообщений
        self.clients = []
        self.messages = []
        # Словарь, содержащий имена пользователей и их сокеты.
        self.names = dict()  # {client_name: client socket}

        super().__init__()

    def init_socket(self):
        SERVER_LOGGER.info(f'Запущен сервер, порт для подключений: {self.port}, '
                           f'адрес, с которого принимаются подключения: {self.addr}, '
                           f'Если адрес не указан, принимаются соединения с любых адресов.')
        # Готовим сокет
        transport = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
        transport.setsockopt(sck.SOL_SOCKET, sck.SO_REUSEADDR, 1)
        transport.bind((self.addr, self.port))
        transport.settimeout(0.5)
        # Слушаем порт
        self.sock = transport
        self.sock.listen()

    def run(self):
        # Инициализация сокета
        self.init_socket()

        # Основнйо цикл
        while True:
            # Ожидание подключения. Исключение по окончании времени.
            try:
                client, client_address = self.sock.accept()
            except OSError:
                pass
            else:
                SERVER_LOGGER.info(f'Установлено соединение с ПК {client_address}')
                self.clients.append(client)

            recv_data_list = []
            send_data_list = []
            err_list = []
            # Проверка на наличие ждущих клиентов
            try:
                if self.clients:
                    recv_data_list, send_data_list, err_list = select.select(self.clients, self.clients, [], 0)
            except OSError:
                pass

            # принимаем сообщения и если ошибка, исключаем клиента.
            if recv_data_list:
                for client_with_message in recv_data_list:
                    try:
                        self.process_client_message(get_message(client_with_message), client_with_message)
                    except:
                        SERVER_LOGGER.info(f'Клиент {client_with_message.getpeername()} '
                                           f'отключился от сервера.')
                        self.clients.remove(client_with_message)

            # Если есть сообщения, обрабатываем каждое.
            for i in self.messages:
                try:
                    self.process_message(i, send_data_list)
                except:
                    SERVER_LOGGER.info(f'Связь с клиентом с именем {i[DESTINATION]} была потеряана.')
                    self.clients.remove(self.names[i[DESTINATION]])
                    del self.names[i[DESTINATION]]
            self.messages.clear()

    def process_message(self, message, listen_socks):
        """
        Функция адресной отправки сообщения определённому клиенту. Принимает словарь сообщение,
        список зарегистрированых пользователей и слушающие сокеты. Ничего не возвращает.
        """
        if message[DESTINATION] in self.names and self.names[message[DESTINATION]] in listen_socks:
            send_message(self.names[message[DESTINATION]], message)
            SERVER_LOGGER.info(f'Отправлено сообщение пользователю {message[DESTINATION]} '
                               f'от пользователя {message[SENDER]}.')
        elif message[DESTINATION] in self.names and self.names[message[DESTINATION]] not in listen_socks:
            raise ConnectionError
        else:
            SERVER_LOGGER.error(
                f'Пользователь {message[DESTINATION]} не зарегистрирован на сервере, '
                f'отправка сообщения невозможна.')

    def process_client_message(self, message, client):
        """
        Обработчик сообщений от клиентов, принимает словарь - сообщение от клиента,
        проверяет корректность, отправляет словарь-ответ в случае необходимости.
        """
        SERVER_LOGGER.debug(f'Разбор сообщения от клиента : {message}')
        # Вариант 1 - сообщение о присутствии + ответ
        if ACTION in message and message[ACTION] == PRESENCE \
                and TIME in message and USER in message:
            # Если такой пользователь еще не зарегистрирован,
            # регистрируем, иначе отправляем ответ и завершаем соединение.
            if message[USER][ACCOUNT_NAME] not in self.names.keys():
                self.names[message[USER][ACCOUNT_NAME]] = client
                client_ip, client_port = client.getpeername()
                self.database.user_login(message[USER][ACCOUNT_NAME], client_ip, client_port)
                send_message(client, RESPONSE_200)
            else:
                response = RESPONSE_400
                response[ERROR] = 'Имя пользователя уже занято.'
                send_message(client, response)
                self.clients.remove(client)
                client.close()
            return
        # Если это сообщение, то добавляем его в очередь сообщений.
        # Ответ не требуется.
        elif ACTION in message and message[ACTION] == MESSAGE and \
                DESTINATION in message and TIME in message \
                and SENDER in message and MESSAGE_TEXT in message:
            self.messages.append(message)
            return
        # Если клиент выходит
        elif ACTION in message and message[ACTION] == EXIT and ACCOUNT_NAME in message:
            self.database.user_logout(message[ACCOUNT_NAME])
            self.clients.remove(self.names[message[ACCOUNT_NAME]])
            self.names[message[ACCOUNT_NAME]].close()
            del self.names[message[ACCOUNT_NAME]]
            return
        # Иначе отдаем Bad request
        else:
            response = RESPONSE_400
            response[ERROR] = 'Запрос некорректен.'
            send_message(client, response)
            return

def print_help():
    print('Поддерживаемые комманды:')
    print('users - список известных пользователей')
    print('connected - писок подключенных пользователей')
    print('loghist - стория входов пользователя')
    print('exit - завершение работы сервера')
    print('help - вывод справки по подерживаемым коммандам')


def main():
    listen_address, listen_port = create_arg_parser()
    database = ServerDB()
    server = Server(listen_address, listen_port, database)
    server.daemon = True
    server.start()

    print_help()

    while True:
        command = input('Введите комманду: ')
        if command == 'help':
            print_help()
        elif command == 'exit':
            break
        elif command == 'users':
            for user in sorted(database.users_list()):
                print(f'Пользователь {user[0]}, последний вход: {user[1]}')
        elif command == 'connected':
            for user in sorted(database.active_users_list()):
                print(f'Пользователь {user[0]}, подключен: {user[1]}:{user[2]}, время установки соединения: {user[3]}')
        elif command == 'loghist':
            name = input('Введите имя пользователя для промотра истории. '
                         'Для вывода всей истории просто нажмите enter: ')
            for user in sorted(database.login_history(name)):
                print(f'Пользователь: {user[0]} время входа: {user[1]}. Вход с: {user[2]}:{user[3]}')
        else:
            print('Команда не распознана.')

if __name__ == '__main__':
    main()
    input('')
