import subprocess

import grpc
import logging

import utils
from probe import Probe
from trojan_gprc_api import *


class TrojanServer:
    def __init__(self, server, port):
        self._trojan = grpc.insecure_channel('{}:{}'.format(server, port))
        self._server_stub = api_pb2_grpc.TrojanServerServiceStub(self._trojan)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _format_trojan_user_list(self, trojan_user):
        new_list = {}
        for user in trojan_user:
            new_list.update(
                {
                    user.status.user.hash: {
                        'ip_current': user.status.ip_current,
                        'ip_limit': user.status.ip_limit,
                        'traffic_total': {
                            'up': user.status.traffic_total.upload_traffic,
                            'down': user.status.traffic_total.download_traffic
                        },
                        'speed_current': {
                            'up': user.status.speed_current.upload_speed,
                            'down': user.status.speed_current.download_speed
                        },
                        'speed_limit': {
                            'up': user.status.speed_limit.upload_speed,
                            'down': user.status.speed_limit.download_speed
                        }
                    }
                }
            )

        return new_list

    def _add_users(self, user):
        request = api_pb2.SetUsersRequest()
        request.status.user.hash = user['sha224uuid']
        request.status.user.password = user['uuid']
        request.status.speed_limit.upload_speed = int(user['speedlimit'])
        request.status.speed_limit.download_speed = int(user['speedlimit'])
        request.status.ip_limit = int(user['iplimit'])
        request.operation = api_pb2.SetUsersRequest.Operation.Add

        yield request

    def _updaet_user(self, user_hash, speed_limit, ip_limit):
        request = api_pb2.SetUsersRequest()
        request.status.user.hash = user_hash

        request.status.speed_limit.upload_speed = int(speed_limit)
        request.status.speed_limit.download_speed = int(speed_limit)
        request.status.ip_limit = int(ip_limit)
        request.operation = api_pb2.SetUsersRequest.Operation.Modify

        yield request

    def _del_user(self, user_hash):
        request = api_pb2.SetUsersRequest()
        request.status.user.hash = user_hash
        request.operation = api_pb2.SetUsersRequest.Operation.Delete

        yield request

    def load_users(self, ssp_users):
        for user, info in ssp_users.items():
            response = self._server_stub.SetUsers(self._add_users(info))
            for r in response:
                logging.debug(r)
        logging.info("用户列表已加载")

    def add_user(self, user):
        logging.info("添加用户 {} to 到服务器".format(user['sha224uuid']))
        response = self._server_stub.SetUsers(self._add_users(user))
        for r in response:
            logging.debug(r)

    def delete_user(self, user_hash):
        logging.info("删除用户 {}".format(user_hash))
        response = self._server_stub.SetUsers(self._del_user(user_hash))
        for r in response:
            logging.debug(r)

    def modify_user(self, user, speedlimit, iplimit):
        response = self._server_stub.SetUsers(self._updaet_user(user, speedlimit, iplimit))
        logging.info("更新用户 {} 限速信息".format(user))
        for r in response:
            logging.debug(r)

    def get_users(self):
        user_status = self._server_stub.ListUsers(api_pb2.ListUsersRequest())
        return self._format_trojan_user_list(user_status)

    def close(self):
        self._trojan.close()


class TrojanClient:
    def __init__(self, server, key, local='localhost:65432', service_name='trojan-go.service', client_path=None):
        self._server = server
        self._key = key
        self._local = local
        self._client_path = client_path
        self._service_name = service_name

        utils.set_logger_format()

    def start(self):
        client = '/opt/trojan-go/trojan-go' if self._client_path is None else self._client_path
        subprocess.Popen([client, '-client', '-password', self._key, '-remote', self._server, '-local', self._local],
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    def get_probe(self):
        return Probe(self._local, self._service_name)
