class SSPanelTrojanGoException(Exception):
    pass


class InvalidTrojanConfiguration(SSPanelTrojanGoException):
    pass


class SSPanelException(SSPanelTrojanGoException):
    pass
