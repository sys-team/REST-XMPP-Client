# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
from session import XMPPSessionThread, XMPPSession

class XMPPSessionPool(object):
    def __init__(self,debug=False,push_sender=None):
        self.session_pool = {}
        self.debug = debug
        self.push_sender = push_sender
        if self.push_sender is not None:
            self.push_sender.start()

    def start_session(self,jid,password,server=None,push_token=None):
        if  self.debug:
            session_id = jid
        else:
            session_id = uuid.uuid4().hex
        self.session_pool[session_id] = XMPPSessionThread(XMPPSession(jid,password,server,push_token,self.push_sender))
        self.session_pool[session_id].start()
        return session_id

    def close_session(self,session_id,with_notification=False):
        session = self.session_pool[session_id]
        session.stop(with_notification)
        session.join(60)
        del self.session_pool[session_id]

    def session_for_id(self,session_id):
        return self.session_pool[session_id].session

    def clean(self):
        for session_key in self.session_pool.keys():
            self.close_session(session_key,with_notification=True)
        if self.push_sender is not None:
            self.push_sender.stop()


class ClientSession(object):
    def __int__(self,xmpp_session,push_token=None,push_sender=None):
        self.xmpp_session = xmpp_session
        self.push_token = push_token
        self.push_sender = push_sender

    def new_message_notification(self,message,unread_count,contact_name,contact_id):
        """Notification from xmpp_session - new message received."""
        pass

    def unread_count_changed(self,unread_count):
        """Notification from xmpp_session - unread count changed."""
        pass