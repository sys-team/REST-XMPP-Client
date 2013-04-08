# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

class XMPPConnectionError(Exception):
    def __init__(self, server):
        self.server = server
    def __str__(self):
        return repr(self.server)

class XMPPAuthError(Exception):
    pass

class XMPPSendError(Exception):
    pass

class XMPPRosterError(Exception):
    pass
