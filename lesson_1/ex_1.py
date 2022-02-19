import platform
import subprocess
import ipaddress
import pprint
import time
result = {'Доступные узлы': '', 'Недоступные узлы': ''}

def check_is_ipaddress(value):
    try:
        ipv4 = ipaddress.ip_address(value)
    except ValueError:
        raise Exception('Некорректный ip адрес.')
    return ipv4

def host_ping(hosts_list, get_list=False):
    print('Начинаем проверку дотупности узлов...')
    for host in hosts_list:
        time.sleep(1)
        try:
            ipv4 = check_is_ipaddress(host)
        except Exception as e:
            print(f'{host} - {e} воспринимаю как доменное имя')
            ipv4 = host

        param = '-n' if platform.system().lower() == 'windows' else '-c'
        response = subprocess.Popen(['ping', param, '1', '-w', '1', str(ipv4)], stdout=subprocess.PIPE)
        if response.wait() == 0:
            result['Доступные узлы'] += f'{ipv4}\n'
            res_string = f'{ipv4} - Узел доступен'
        else:
            result['Недоступные узлы'] += f'{ipv4}\n'
            res_string = f'{ipv4} - Узел недоступен'
        if not get_list:
            print(res_string)
    if get_list:
        return result

if __name__ == '__main__':
    hosts_list = ['192.168.8.1', '8.8.8.8', 'yandex.ru', 'google.com', '111.111.111.11.11',
                  '0.0.0.1', '0.0.0.1', '0.0.0.1', '0.0.0.1',
                  '0.0.0.1', '0.0.0.1', '0.0.0.1', '0.0.0.1',]
    start = time.time()
    host_ping(hosts_list)
    end = time.time()
    print(f'total time: {int(end - start)}')
    pprint.pprint(result)
