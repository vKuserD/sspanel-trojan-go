import functools
import hashlib

from requests.adapters import HTTPAdapter, Retry

import utils
from exception import InvalidTrojanConfiguration, SSPanelException


class SSPanel:
    def __init__(self, _api, _key, _node_id, timeout=2):
        self._api = _api
        self._key = _key
        self._node_id = _node_id
        self._speed_limit = 0

        self._requests = utils.create_http_session(self._get_http_adapter())
        self._requests.request = functools.partial(self._requests.request, timeout=timeout)

    @staticmethod
    def _get_http_adapter():
        return HTTPAdapter(
            max_retries=Retry(
                total=5,
                backoff_factor=0.5,
                method_whitelist=frozenset(['GET'])
            )
        )

    def _format_user_list(self, ssp_user):
        new_list = {}
        for user in ssp_user:
            if 'uuid' in user:
                # 计算sha224
                sha224 = hashlib.sha224(user['uuid'].encode()).hexdigest()
                # 单位转换
                speed_limit = user['node_speedlimit'] if self._speed_limit == 0 else self._speed_limit
                if self._speed_limit != 0 and user['node_speedlimit'] != 0:
                    speed_limit = min(self._speed_limit, user['node_speedlimit'])
                new_list.update(
                    {
                        sha224: {
                            'id': user['id'],
                            'sha224uuid': sha224,
                            'uuid': user['uuid'],
                            'speedlimit': int(speed_limit * 125_000),
                            'iplimit': user['node_connector']
                        }
                    }
                )
            else:
                raise InvalidTrojanConfiguration(
                    "缺少 'uuid' 字段, 请确保在SSPanel中将节点类型设置为Trojan")

        return new_list

    @staticmethod
    def _validator(response):
        if response.status_code != 200:
            raise SSPanelException("服务器返回了 http 状态码 {}".format(response.status_code))
        _json = response.json()
        if _json['ret'] != 1:
            error_msg = "SSPanel返回的状态不为 1"
            if _json['data']:
                error_msg += ", 错误: {} ".format(_json['data'])

            raise SSPanelException(error_msg)

        return _json['data']

    def _get_api(self, api_url):
        return api_url.format(self._api, self._key, self._node_id)

    def load_node_info(self):
        response = self._requests.get(self._get_api('{0}/mod_mu/nodes/{2}/info?key={1}&node_id={2}'))
        json_data = self._validator(response)
        self._speed_limit = json_data['node_speedlimit']

    def get_users(self):
        response = self._requests.get(self._get_api('{}/mod_mu/users?key={}&node_id={}'))
        json_data = self._validator(response)

        return {} if json_data is None else self._format_user_list(json_data)

    def add_traffic(self, traffic_data):
        response = self._requests.post(self._get_api('{}/mod_mu/users/traffic?key={}&node_id={}'), json=traffic_data,
                                       timeout=30)

        return self._validator(response)

    def add_alive_ip(self, user_list):
        response = self._requests.post(self._get_api('{}/mod_mu/users/aliveip?key={}&node_id={}'), json=user_list)

        return self._validator(response)

    def add_node_info(self, load, uptime):
        post_data = {'load': load, 'uptime': uptime}
        response = self._requests.post(
            self._get_api('{0}/mod_mu/nodes/{2}/info?key={1}&node_id={2}'), json=post_data)

        return self._validator(response)
