# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
import xmpp
import logging
import time
import socket
import threading
from secure_client import XMPPSecureClient
from message_store import XMPPMessagesStore
from errors import XMPPAuthError, XMPPConnectionError, XMPPRosterError, XMPPSendError

from  notificators import XMPPPollNotification, XMPPPushNotification

class XMPPSession():
    def __init__(self,jid,password,server=None,push_token=None):
        self.token = uuid.uuid4().hex
        self.jid = xmpp.protocol.JID(jid)
        if  server is None:
            server = self.jid.getDomain()
        self.password=password
        self.server = server
        self.client = XMPPSecureClient(self.jid.getDomain(),debug = [])
        self.client.RegisterDisconnectHandler(self.reconnect)
        self.client.UnregisterDisconnectHandler(self.client.DisconnectHandler)
        self.messages_store = XMPPMessagesStore()
        self.push_notifier = None
        if push_token is not None:
            self.push_notifier = XMPPPushNotification(push_token)
        self.poll_notifier = XMPPPollNotification()
        self.new_messages_count = 0

        self.setup_connection()

    def clean(self):
        logging.debug('%s: SessionEvent : Session %s start cleaning', time.ctime(),self.jid)
        self.client.UnregisterDisconnectHandler(self.reconnect)
        self.client.Dispatcher.disconnect()

        self.poll_notifier.stop()
        if self.push_notifier is not None:
            self.push_notifier.stop()
            self.push_notifier.join(0)

        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']
            try:
                sock._sock.shutdown(socket.SHUT_RDWR)
            except:
                logging.debug('%s: SessionEvent : Session %s socket shutdowned', time.ctime(), self.jid)
            sock._sock.close()
            sock.PlugOut()

        logging.debug('%s: SessionEvent : Session %s cleaning done',time.ctime(), self.jid)

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
        self.client.Dispatcher.RegisterHandler('message',self.xmpp_message)
        self.client.Dispatcher.RegisterDefaultHandler(self.debugging_handler)

    def debugging_handler(self, con, event):
        try:
            logging.debug('%s : XMPPEvent : %s',time.ctime(),event)
        except UnicodeEncodeError:
            logging.debug('%s : XMPPEvent : UnicodeEncodeError Exception',time.ctime())

    def xmpp_presence(self, con, event):
        self.poll_notifier.notify()

    def xmpp_message(self, con, event):
        type = event.getType()
        jid_from = event.getFrom().getStripped()
        contact_id = self.client.getRoster().itemId(jid_from)

        message_text = event.getBody()
        if  message_text is not None:
            self.messages_store.append_message(jid=contact_id,inbound=True,id=event.getID(),text=message_text)
            self.new_messages_count+=1
            self.poll_notifier.notify()
            if self.push_notifier is not None:
                contact = self.client.getRoster().getItem(contact_id)
                message = ''.join([contact['name'],': \n',message_text])
                self.push_notifier.notify(message=message,unread_count=self.new_messages_count)

    def setup_connection(self):
        if not self.client.isConnected():
            logging.debug('%s: SessionEvent : Session %s Setup connection',time.ctime(),self.jid)
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
            logging.debug('%s: SessionEvent : Session %s Reconnect',time.ctime(),self.jid)
            self.client.reconnectAndReauth()
        self.client.sendInitPresence()
        self.client.getRoster()

    def reset_new_messages_counter(self):
        self.new_messages_count = 0

    def send(self,contact_id,message):
        jid = self.client.getRoster().getItem(contact_id)['jid']
        return self.sendByJID(jid,message)

    def sendByJID(self,jid,message):
        self.setup_connection()
        if self.client.isConnected():
            id = self.client.send(xmpp.protocol.Message(jid,message))
            if not id:
                raise XMPPSendError()

            contact_id = self.client.getRoster().itemId(jid)
            result = self.messages_store.append_message(jid=contact_id,inbound=False,id=id,text=message)
            self.poll_notifier.notify()
            return result
        else:
            raise XMPPSendError()


    def contacts(self,timestamp=None):
        if not self.client.isConnected():
            raise XMPPRosterError()

        roster = self.client.getRoster().getRawRoster().values()
        if  timestamp is not None:
            roster = filter(lambda contact: contact['timestamp'] > timestamp,roster)

        return roster

    def contact(self,contact_id):
        if self.client.isConnected():
            contact = self.client.getRoster().getItem(contact_id)
            if  contact is None:
                raise KeyError
            else:
                return contact
        else:
            raise XMPPRosterError()

    def contactByJID(self,jid):
        if self.client.isConnected():
            return self.client.getRoster().getItemByJID(jid)
        else:
            raise XMPPRosterError()

    def messages(self,contact_ids=None,timestamp=None):
        return self.messages_store.messages(jids=contact_ids,timestamp=timestamp)

    def add_contact(self,jid):
        self.client.getRoster().Subscribe(jid)
        self.client.Dispatcher.Process(0.5)

    def remove_contact(self,contact_id):
        jid = self.client.getRoster().getItem(contact_id)['jid']
        self.client.getRoster().Unauthorize(jid)
        self.client.getRoster().Unsubscribe(jid)
        self.client.getRoster().delItem(jid)

    def authorize_contact(self,contact_id):
        jid = self.client.getRoster().getItem(contact_id)['jid']
        self.client.getRoster().Authorize(jid)
        self.client.Dispatcher.Process(0.5)

    def unauthorize_contact(self,contact_id):
        jid = self.client.getRoster().getItem(contact_id)['jid']
        self.client.getRoster().Unauthorize(jid)

    def poll_changes(self):
        return self.poll_notifier.poll()


class XMPPSessionThread(threading.Thread):
    """Threaded XMPP session"""
    def __init__(self, session):
        super(XMPPSessionThread, self).__init__()
        self.session = session
        self.keepRunning = True

    def run(self):
        while self.keepRunning:
            self.session.client.Process(1)
            #time.sleep(1)

        self.session.clean()

    def stop(self):
        self.keepRunning = False