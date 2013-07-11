# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
import xmpp
import logging
import threading
from secure_client import XMPPSecureClient
from  notificators import XMPPPollNotification

class XMPPSession(object):
    def __init__(self,jid,password,server=None,push_token=None,push_sender=None):
        self.token = uuid.uuid4().hex
        self.push_sender = push_sender
        self.push_token = push_token
        self.jid = xmpp.protocol.JID(jid)
        self.password=password

        if  server is None:
            server = self.jid.getDomain()
        server_port = server.split(':')
        server = server_port[0]
        if len(server_port) > 1:
            port = int(server_port[1])
        else:
            port = 5222

        self.client = XMPPSecureClient(jid=jid,password=password,server=server,port=port)
        self.poll_notifier = XMPPPollNotification()

        self.setup_connection()

    def clean(self,with_notification=True):
        if   with_notification:
            self.push_sender.notify(token=self.push_token,message="Session closed. Login again, to start new session.",unread_count=0)
        logging.debug(u'SessionEvent : Session %s start cleaning',self.jid)
        self.client.disconnect()
        self.poll_notifier.stop()
        logging.debug(u'SessionEvent : Session %s cleaning done', self.jid)

    def register_handlers(self):
        self.client.Dispatcher.RegisterHandler('presence',self.xmpp_presence)
        self.client.Dispatcher.RegisterHandler('iq',self.xmpp_presence)
        self.client.Dispatcher.RegisterHandler('message',self.xmpp_message)

    def xmpp_presence(self, con, event):
        self.poll_notifier.notify()

    def xmpp_message(self, con, event):
        type = event.getType()
        jid_from = event.getFrom().getStripped()
        contact_id = self.client.getRoster().itemId(jid_from)
        contact = self.client.getRoster().getItem(contact_id)
        message_text = event.getBody()
        
        if  message_text is not None and contact is not None:
            self.poll_notifier.notify()
            if self.push_sender is not None:
                self.push_sender.notify(token=self.push_token,message=None,unread_count=self.client.unread_count(),contact_name=contact['name'],contact_id=contact_id)

    def setup_connection(self):
        if not self.client.isConnected():
            self.client.setup_connection()
            self.register_handlers()
            self.client.sendInitPresence()
            self.client.getRoster()

    def messages(self,contact_ids=None,event_offset=None):
        return self.client.messages(contact_ids=contact_ids,event_offset=event_offset)

    def send(self,contact_id,message):
        return self.client.send_message(contact_id=contact_id,message=message)

    def send_by_jid(self,jid,message):
        return self.client.send_message_by_jid(jid=jid,message=message)

    def contacts(self,event_offset=None):
        return self.client.contacts(event_offset=event_offset)

    def contact(self,contact_id):
        return self.client.contact(contact_id)

    def add_contact(self,jid,name=None,groups=[]):
        self.client.add_contact(jid=jid,name=name,groups=groups)

    def update_contact(self,contact_id,name=None,groups=None):
        self.client.update_contact(contact_id=contact_id,name=name,groups=groups)

    def set_contact_read_offset(self,contact_id,read_offset):
        self.client.set_contact_read_offset(contact_id=contact_id,read_offset=read_offset)
        self.poll_notifier.notify()
        self.push_sender.notify(token=self.push_token,unread_count=self.client.unread_count())

    def set_contact_authorization(self,contact_id,authorization):
        self.client.set_contact_authorization(contact_id=contact_id,authorization=authorization)

    def contact_by_jid(self,jid):
        self.client.contact_by_jid(jid=jid)

    def remove_contact(self,contact_id):
        self.client.remove_contact(contact_id=contact_id)

    def poll_changes(self):
        return self.poll_notifier.poll()


class XMPPSessionThread(threading.Thread):
    """Threaded XMPP session"""
    def __init__(self, session):
        super(XMPPSessionThread, self).__init__()
        self.session = session
        self.keepRunning = True
        self.with_notification = True

    def run(self):
        while self.keepRunning:
            try:
                self.session.client.Process(1)
            except xmpp.protocol.StreamError:
                self.session.client.Dispatcher.disconnect()

        self.session.clean(with_notification=self.with_notification)

    def stop(self,with_notification=True):
        self.with_notification = with_notification
        self.keepRunning = False