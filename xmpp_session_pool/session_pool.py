# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
from session import XMPPSession, XMPPClientThread
from secure_client import XMPPSecureClient
from errors import XMPPAuthError

class XMPPSessionPool(object):
    def __init__(self,debug=False,push_sender=None):
        self.session_pool = {}
        self.client_pool = {}
        self.debug = debug
        self.push_sender = push_sender
        if self.push_sender is not None:
            self.push_sender.start()

    def start_session(self,jid,password,server=None,push_token=None):
        if  self.debug:
            session_id = jid
        else:
            session_id = uuid.uuid4().hex

        if jid not in self.client_pool:
            client_thread = XMPPClientThread(XMPPSecureClient(jid=jid,password=password,server=server))
            client_thread.start()
            self.client_pool[jid] = client_thread
        else:
            client_thread = self.client_pool[jid]
            if not client_thread.client.check_credentials(jid,password):
                raise XMPPAuthError

        self.session_pool[session_id] = XMPPSession(client_thread.client,push_token,self.push_sender)
        return session_id

    def close_session(self,session_id,with_notification=False):
        session = self.session_pool[session_id]
        client_thread = None
        if session.client.jid in self.client_pool:
            client_thread = self.client_pool[session.client.jid]

        session.clean(with_notification=with_notification)
        del self.session_pool[session_id]

        if  client_thread is not None and client_thread.is_alive and not client_thread.client.observers_count:
            client_thread.stop()
            client_thread.join(60)
            del self.client_pool[session.client.jid]

    def session_for_id(self,session_id):
        return self.session_pool[session_id]

    def clean(self):
        for session_key in self.session_pool.keys():
            self.close_session(session_key,with_notification=True)
        if self.push_sender is not None:
            self.push_sender.stop()