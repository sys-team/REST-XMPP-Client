# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
import xmpp
import logging
import socket
import threading
from secure_client import XMPPSecureClient
from message_store import XMPPMessagesStore
from errors import XMPPAuthError, XMPPConnectionError, XMPPRosterError, XMPPSendError
from event_id import XMPPSessionEventID
from  notificators import XMPPPollNotification

class XMPPSession(object):
    def __init__(self,jid,password,server=None,push_token=None,push_sender=None):
        self.id_generator = XMPPSessionEventID()
        self.token = uuid.uuid4().hex
        self.push_sender = push_sender
        self.push_token = push_token
        self.jid = xmpp.protocol.JID(jid)
        if  server is None:
            server = self.jid.getDomain()
        self.password=password
        self.server = server
        self.client = XMPPSecureClient(self.id_generator,self.jid.getDomain(),debug = [])
        self.client.RegisterDisconnectHandler(self.reconnect)
        self.client.UnregisterDisconnectHandler(self.client.DisconnectHandler)
        self.messages_store = XMPPMessagesStore()
        self.poll_notifier = XMPPPollNotification()
        self.new_messages_count = 0

        self.setup_connection()

    def clean(self,with_notification=True):
        if   with_notification:
            self.push_sender.notify(token=self.push_token,message="Session closed. Login again, to start new session.",unread_count=0)
        logging.debug(u'SessionEvent : Session %s start cleaning',self.jid)
        self.client.UnregisterDisconnectHandler(self.reconnect)
        self.client.Dispatcher.disconnect()

        self.poll_notifier.stop()

        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']
            try:
                sock._sock.shutdown(socket.SHUT_RDWR)
            except:
                logging.debug(u'SessionEvent : Session %s socket shutdowned', self.jid)
            sock._sock.close()
            sock.PlugOut()

        logging.debug(u'SessionEvent : Session %s cleaning done', self.jid)

    def server_tuple(self):
        server_port = self.server.split(':')
        server = server_port[0]
        if len(server_port) > 1:
            port = int(server_port[1])
        else:
            port = 5222

        return server,port

    def register_handlers(self):
        self.client.Dispatcher.RegisterHandler('presence',self.xmpp_presence)
        self.client.Dispatcher.RegisterHandler('iq',self.xmpp_presence)
        self.client.Dispatcher.RegisterHandler('message',self.xmpp_message)
        self.client.Dispatcher.RegisterDefaultHandler(self.debugging_handler)

    def debugging_handler(self, con, event):
        logging.debug(u'XMPPEvent : %s ',event)

    def xmpp_presence(self, con, event):
        self.poll_notifier.notify()

    def xmpp_message(self, con, event):
        type = event.getType()
        jid_from = event.getFrom().getStripped()
        contact_id = self.client.getRoster().itemId(jid_from)
        contact = self.client.getRoster().getItem(contact_id)
        message_text = event.getBody()
        
        if  message_text is not None and contact is not None:
            self.messages_store.append_message(contact_id=contact_id,inbound=True, event_id=self.id_generator.id(),text=message_text)
            self.poll_notifier.notify()
            if self.push_sender is not None:
                self.push_sender.notify(token=self.push_token,message=None,unread_count=self.unread_count(),contact_name=contact['name'],contact_id=contact_id)

    def unread_count(self):
        unread_count = 0
        for contact in self.client.getRoster().getRawRoster().values():
            if (contact['id'] in self.messages_store.chats_store
                and contact['read_offset'] < self.messages_store.chats_store[contact['id']][-1]['event_id']):
                unread_count += 1

        return unread_count

    def setup_connection(self):
        if not self.client.isConnected():
            logging.debug('SessionEvent : Session %s Setup connection',self.jid)
            con = self.client.connect(server=self.server_tuple())

            if not self.client.isConnected() or con is None:
                raise XMPPConnectionError(self.server)

            auth = self.client.auth(self.jid.getNode(),self.password,resource = self.jid.getResource())
            if not auth:
                raise XMPPAuthError()

            self.register_handlers()
            self.client.sendInitPresence()
            self.client.getRoster()

    def reconnect(self):
        while not self.client.isConnected():
            logging.debug(u'SessionEvent : Session %s Reconnect',self.jid)
            self.client.reconnectAndReauth()
        self.client.sendInitPresence()
        self.client.getRoster()

    def send(self,contact_id,message):
        jid = self.client.getRoster().getItem(contact_id)['jid']
        return self.send_by_jid(jid,message)

    def send_by_jid(self,jid,message):
        self.setup_connection()
        if self.client.isConnected():
            id = self.client.send(xmpp.protocol.Message(to=jid,body=message,typ='chat'))
            if not id:
                raise XMPPSendError()

            contact_id = self.client.getRoster().itemId(jid)
            result = self.messages_store.append_message(contact_id=contact_id,inbound=False, event_id=self.id_generator.id(),text=message)
            self.poll_notifier.notify()
            return result
        else:
            raise XMPPSendError()

    def contacts(self,event_offset=None):
        if not self.client.isConnected():
            raise XMPPRosterError()

        return self.client.getRoster().getContacts(event_offset=event_offset)

    def contact(self,contact_id):
        if self.client.isConnected():
            contact = self.client.getRoster().getItem(contact_id)
            if  contact is None:
                raise KeyError
            else:
                return contact
        else:
            raise XMPPRosterError()

    def add_contact(self,jid,name=None,groups=[]):
        if self.client.isConnected():
            self.client.getRoster().setItem(jid,name=name,groups=groups)
            self.client.getRoster().Subscribe(jid)

    def update_contact(self,contact_id,name=None,groups=None):
        if self.client.isConnected():
            self.client.getRoster().updateItem(contact_id,name=name,groups=groups)

    def set_contact_read_offset(self,contact_id,read_offset):
        self.client.getRoster().setItemReadOffset(contact_id,read_offset)
        self.poll_notifier.notify()
        self.push_sender.notify(token=self.push_token,unread_count=self.unread_count())

    def set_contact_authorization(self,contact_id,authorization):
        contact = self.client.getRoster().getItem(contact_id)
        if contact is None or contact['authorization'] == authorization:
            return

        if  authorization == 'granted':
            self.add_contact(contact['jid'])
            self.client.getRoster().Authorize(contact['jid'])
        elif authorization == 'none':
            self.client.getRoster().Unauthorize(contact['jid'])


    def contact_by_jid(self,jid):
        if self.client.isConnected():
            return self.client.getRoster().getItemByJID(jid)
        else:
            raise XMPPRosterError()

    def messages(self,contact_ids=None,event_offset=None):
        return self.messages_store.messages(contact_ids=contact_ids, event_offset=event_offset)

    def remove_contact(self,contact_id):
        item = self.client.getRoster().getItem(contact_id)
        if item is not None:
            jid = self.client.getRoster().getItem(contact_id).get('jid')
            if  jid is not None:
                self.client.getRoster().delItem(jid)
        self.messages_store.remove_messages_for_conatct(contact_id)

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