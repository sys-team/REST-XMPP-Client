# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
from session import XMPPSessionThread, XMPPSession

class XMPPSessionPool():
    def __init__(self,debug=False):
        self.session_pool = {}
        self.debug = debug

    def start_session(self,jid,password,server=None,push_token=None):
        if  self.debug:
            session_id = jid
        else:
            session_id = uuid.uuid4().hex
        self.session_pool[session_id] = XMPPSessionThread(XMPPSession(jid,password,server,push_token))
        self.session_pool[session_id].start()
        return session_id

    def close_session(self,session_id):
        session = self.session_pool[session_id]
        session.stop()
        session.join(0)
        del self.session_pool[session_id]

    def session_for_id(self,session_id):
        return self.session_pool[session_id].session

    def clean(self):
        for session_key in self.session_pool.keys():
            self.close_session(session_key)

    def __del__(self):
        self.clean()