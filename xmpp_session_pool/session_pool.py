# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
from session import XMPPSession
from xmpp_client import XMPPClient
from errors import XMPPAuthError
import xmpp_inbound_dispatchers


class XMPPSessionPool(object):
    def __init__(self, debug=False, push_sender=None):
        self.session_pool = {}
        self.xmpp_client_pool = {}
        self.im_client_pool = {}
        self.debug = debug
        self.push_sender = push_sender
        if self.push_sender is not None:
            self.push_sender.start()

    def start_session(self, jid, password, server=None, push_token=None, im_client_id=None):
        if jid not in self.xmpp_client_pool:
            xmpp_client = XMPPClient(jid=jid, password=password, server=server)
            xmpp_client.setup_connection()
            xmpp_dispatcher = xmpp_inbound_dispatchers.XMPPTornadoMainIOLoopDispatcher(xmpp_client)
            xmpp_dispatcher.start()

            self.xmpp_client_pool[jid] = xmpp_dispatcher
        else:
            xmpp_dispatcher = self.xmpp_client_pool[jid]
            if not xmpp_dispatcher.client.check_credentials(jid, password):
                raise XMPPAuthError

        if im_client_id is None:
            im_client_id = uuid.uuid4().hex

        if im_client_id not in self.im_client_pool:
            self.im_client_pool[im_client_id] = IMClient(client_id=im_client_id, push_token=push_token, push_sender=self.push_sender)

        im_client = self.im_client_pool[im_client_id]

        session = im_client.start_session(jid=jid, xmpp_client=xmpp_dispatcher.client)
        if session.session_id not in self.session_pool:
            self.session_pool[session.session_id] = session

        return session.session_id

    def close_session(self,session_id,with_notification=False):
        session = self.session_pool[session_id]
        im_client = session.im_client

        if session.xmpp_client.jid in self.xmpp_client_pool:
            xmpp_dispatcher = self.xmpp_client_pool[session.xmpp_client.jid]

        if len(im_client.sessions) and im_client.client_id in self.im_client_pool:
            del self.im_client_pool[im_client.client_id]

        session.clean(with_notification=with_notification)
        del self.session_pool[session_id]

        if  xmpp_dispatcher is not None and not xmpp_dispatcher.client.observers_count:
            xmpp_dispatcher.stop()
            del self.xmpp_client_pool[session.xmpp_client.jid]

    def session_for_id(self,session_id):
        return self.session_pool[session_id]

    def clean(self):
        for session_key in self.session_pool.keys():
            self.close_session(session_key,with_notification=True)
        if self.push_sender is not None:
            self.push_sender.stop()


class IMClient(object):
    def __init__(self, client_id, push_token=None, push_sender=None):
        self.client_id = client_id
        self.sessions = {}
        self.push_token = push_token
        self.push_sender = push_sender

    def start_session(self, jid, xmpp_client):
        if jid not in self.sessions:
            self.sessions[jid] = XMPPSession(session_id=uuid.uuid4().hex, xmpp_client=xmpp_client, im_client=self)
        return self.sessions[jid]

    def session_closed(self, session):
        del self.sessions[session.jid]

    def push_notification(self, message=None, contact_name=None, contact_id=None, sound=True):
        if self.push_token is None or self.push_sender is None:
            return
        unread_count = sum(session.unread_count for session in self.sessions.values())
        self.push_sender.notify(token=self.push_token, message=message, unread_count=unread_count,
                                contact_name=contact_name, contact_id=contact_id, sound=sound)