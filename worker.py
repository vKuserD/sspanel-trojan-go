import hashlib
import os
import subprocess
import threading
import time
import logging

import psutil
import requests
from grpc import RpcError

import utils
from exception import SSPanelTrojanGoException
from probe import Probe
from sspanel import SSPanel
from trojan import TrojanServer, TrojanClient


class Worker:
    def __init__(self, config):
        self._config = config
        ssp_config = self._config['sspanel']
        self._sspanel = SSPanel(ssp_config.get('api'), ssp_config.get('key'), ssp_config.getint('id'))
        self._executor = None
        self._probe_user = None
        self._terminated = threading.Event()
        self._lock = threading.Lock()
        self._user_cache = {}
        self._last_data_usage = None

    def _connect_trojan_server(self):
        return TrojanServer(self._config['trojan_server'].get('hostname'), self._config['trojan_server'].get('port'))

    @staticmethod
    def _get_probe_user():
        password = utils.get_random_password(64)
        sha224_password = hashlib.sha224(password.encode()).hexdigest()

        return {'sha224uuid': sha224_password, 'uuid': password, 'speedlimit': 0, 'iplimit': 0,
                'email': 'probe@example.com'}

    def _run_probe(self):
        logging.info("Probe thread started")
        probe_config = self._config['probe']
        probe = Probe('localhost:{}'.format(self._config['trojan_client'].get('local_port')))

        self._terminated.wait(10)
        while not self._terminated.is_set():
            try:
                with self._connect_trojan_server() as trojan_server:
                    if self._probe_user['sha224uuid'] not in trojan_server.get_users():
                        trojan_server.add_user(self._probe_user)
                    probe.test(probe_config.get('test_url'))
            except Exception as e:
                if self._config['probe'].getboolean('auto_restart'):
                    logging.debug(e)
                    logging.error('无法检测 Trojan-go 状态, 重启服务。')
                    subprocess.check_output('systemctl restart {}'.format(probe_config.get('service')), shell=True,
                                            stderr=subprocess.DEVNULL)
                else:
                    logging.error('无法检测Trojan-go 状态, 错误: {}', e)
            finally:
                self._terminated.wait(probe_config.getint('interval'))

    def _update_user_cache(self, user_list):
        for user in user_list.values():
            self._user_cache.update({user['sha224uuid']: user['id']})

    def _get_last_usage(self, sha224_hash):
        if sha224_hash in self._last_data_usage:
            return self._last_data_usage[sha224_hash]
        else:
            return {'upload': 0, 'download': 0}

    def _generate_ssp_node_usage(self, data_usage):
        # 当没有历史数据的时候，汇报空数据
        if None is data_usage or None is self._last_data_usage:
            return []

        # 计算流量差值
        traffic_data = []
        for sha224_hash, data in data_usage.items():
            if data['upload'] != 0 or data['download'] != 0:
                last_data = self._get_last_usage(sha224_hash)
                diff_uploaded = int((data['upload'] - last_data['upload']))
                diff_downloaded = int((data['download'] - last_data['download']))
                if diff_uploaded != 0 or diff_downloaded != 0:
                    traffic_data.append({'user_id': data['id'], 'u': diff_uploaded, 'd': diff_downloaded})

        return traffic_data

    @staticmethod
    def _get_node_info():
        load_avg = '{} {} {}'.format(*os.getloadavg())
        uptime = time.time() - psutil.boot_time()

        return [load_avg, uptime]

    def _run_updater(self):
        logging.debug("thread lock %s", self._lock.locked())
        self._lock.acquire(timeout=(self._config['sspanel'].getint('interval') - 5))

        with self._connect_trojan_server() as connection:
            try:
                data_usage = self._get_user_usage(connection)
                node_usage = self._generate_ssp_node_usage(data_usage)
                self._sspanel.add_traffic({'data': node_usage})
                self._last_data_usage = data_usage
                user_count = len(node_usage)
                if user_count != 0:
                    logging.info('{} 个用户流量数据已上传'.format(user_count))
                self._sspanel.add_node_info(*self._get_node_info())
            except SSPanelTrojanGoException as e:
                logging.error(e)
            except requests.exceptions.RequestException as e:
                logging.error(e)
            except RpcError as e:
                logging.error("无法连接到 the Trojan-go, 错误代码 %s, 信息: %s", e.code(), e.details())
            except Exception as e:
                logging.exception("未知错误")

        self._lock.release()

    def _get_user_usage(self, connection):
        self._sspanel.load_node_info()
        ssp_users = self._sspanel.get_users()
        ssp_user_hash = list(ssp_users.keys())
        trojan_user = connection.get_users()
        trojan_user_hash = list(trojan_user.keys())

        # 更新用户列表缓存
        self._update_user_cache(ssp_users)

        # 自动过滤探针用户
        if None is not self._probe_user:
            if self._probe_user and self._probe_user['sha224uuid'] in trojan_user:
                del trojan_user[self._probe_user['sha224uuid']]
                trojan_user_hash.remove(self._probe_user['sha224uuid'])

        # 如果用户列表是空的，则把所有用户都加入到列表中，列表最小为1
        if len(trojan_user) < 2:
            connection.load_users(ssp_users)
            return None

        # 添加新的用户
        new_user_list = list(set(ssp_user_hash) - set(trojan_user_hash))
        for user in new_user_list:
            connection.add_user(ssp_users[user])
            del ssp_users[user]
            ssp_user_hash.remove(user)

        # 需要删除的用户
        user_delete_list = list(set(trojan_user_hash) - set(ssp_user_hash))
        for user in user_delete_list:
            connection.delete_user(user)

        # 需要更新数据的用户
        for user_hash, s_user in ssp_users.items():
            t_user = trojan_user[user_hash]
            if int(t_user['speed_limit']['up']) != int(s_user['speedlimit']) or int(t_user['ip_limit']) != int(
                    s_user['iplimit']):
                connection.modify_user(user_hash, s_user['speedlimit'], s_user['iplimit'])

        # 创建流量表
        data_usage = {}
        for user_hash, data in trojan_user.items():
            user_id = None
            if user_hash in ssp_users:
                user_id = ssp_users[user_hash]['id']
            if user_hash in self._user_cache:
                user_id = self._user_cache[user_hash]
            if user_id is not None:
                data_usage.update(
                    {
                        user_hash: {
                            'id': user_id,
                            'upload': data['traffic_total']['up'],
                            'download': data['traffic_total']['down'],
                            'ip_count': data['ip_current']
                        }
                    }
                )

        # 删除用户缓存
        for user in user_delete_list:
            if user in self._user_cache:
                del self._user_cache[user]

        return data_usage

    def run(self):
        # 是否启动Trojan探针
        if self._config['probe'].getboolean('enabled'):
            tc_config = self._config['trojan_client']
            self._probe_user = self._get_probe_user()
            probe_local = 'localhost:{}'.format(tc_config.get('local_port'))
            client_remote = '{}:{}'.format(tc_config.get('remote_host'), tc_config.get('remote_port'))
            trojan_client = TrojanClient(client_remote, self._probe_user['uuid'], probe_local,
                                         tc_config.get('service'), tc_config.get('executable'))
            trojan_client.start()

            probe = utils.create_thread(self._run_probe, 'Probe')
            probe.start()

        # 启动主更新线程
        while not self._terminated.is_set():
            updater = utils.create_thread(self._run_updater, 'Updater')
            updater.start()
            self._terminated.wait(self._config['sspanel'].getint('interval'))

    def terminate(self):
        self._terminated.set()
