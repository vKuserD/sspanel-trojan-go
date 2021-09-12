#!/usr/bin/env python3
import argparse
import configparser
import logging
from multiprocessing import Process

import signal

import utils
from worker import Worker

_worker_process = None


def arg_parser():
    parser = argparse.ArgumentParser(description='SSPanel trojan-go')
    parser.add_argument('--config', required=True, help='Config file path')

    return parser.parse_args()


def signal_handler(_signal, frame):
    global _worker_process
    if None is not _worker_process:
        _worker_process.terminate()


def create_worker(config):
    utils.set_logger_format()
    worker = Worker(config)
    worker.run()


def main():
    # get all args
    args = arg_parser()

    # read config
    config = configparser.ConfigParser()
    config.read(args.config)

    # start worker process
    global _worker_process
    _worker_process = Process(target=create_worker, args=(config,))
    _worker_process.daemon = True

    logging.info("SSPanel-Trojan-go started")
    _worker_process.start()
    _worker_process.join()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGQUIT, signal_handler)

    utils.set_logger_format()
    main()
