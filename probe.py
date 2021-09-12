import logging

from requests.adapters import HTTPAdapter, Retry

import utils


class Probe:
    def __init__(self, local, service_name='trojan-go.service'):
        utils.set_logger_format()
        self._http = utils.create_http_session(self._get_http_adapter())
        socks5_proxy = 'socks5://{}'.format(local)
        self._proxy = {'http': socks5_proxy, 'https': socks5_proxy}
        self._service_name = service_name

    @staticmethod
    def _get_http_adapter():
        return HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"]
            )
        )

    def test(self, probe_url):
        self._http.get(probe_url, proxies=self._proxy, timeout=5)
        logging.debug('trojan-go is working')
