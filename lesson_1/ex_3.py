from ex_2 import host_range_ping
from ex_1_thread import check_is_ipaddress, host_ping, hosts_threading
from tabulate import tabulate

def host_range_ping_tab():
    res_dict = host_range_ping(True)
    print()
    print(tabulate([res_dict], headers='keys', tablefmt='pipe', stralign='center'))

if __name__ == '__main__':
    host_range_ping_tab()