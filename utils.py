import random

import string

import logging
import threading

import requests


def get_random_password(length=16):
    return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=length))


def set_logger_format():
    # set logger
    logging.basicConfig(
        format='%(asctime)s [%(processName)s] [%(threadName)s] [%(levelname)8s]  %(message)s',
        level=logging.INFO,
        handlers=[logging.StreamHandler()]
    )


def create_thread(target, name):
    new_thread = threading.Thread(target=target)
    new_thread.setName(name)

    return new_thread


def create_http_session(adapter):
    request_session = requests.Session()
    request_session.mount('https://', adapter)
    request_session.mount('http://', adapter)

    return request_session
