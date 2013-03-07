# -*- coding: utf-8 -*-

__author__ = 'kovtash'

import xmpp
import os
import logging
import threading
import inspect
import socket

from bottle import PluginError

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

class XMPPSession():
    def __init__(self,jid,password,server=None):
        self.jid = xmpp.protocol.JID(jid)
        if  server is None:
            server = self.jid.getDomain()
        self.password=password
        self.server = server
        self.client = xmpp.Client(self.jid.getDomain(),debug = [])
        self.messages_store = {}
        self.client.RegisterDisconnectHandler(self.setup_connection)
        self.client.UnregisterDisconnectHandler(self.client.DisconnectHandler)
        self.setup_connection()

    def clean(self):
        logging.info('Session %s start cleaning', self.jid)
        self.client.UnregisterDisconnectHandler(self.setup_connection)

        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']
            sock._sock.shutdown(socket.SHUT_RDWR)
            sock._sock.close()
            sock.PlugOut()

        logging.info('Session %s cleaning done',self.jid)
        
    def server_tuple(self):
        server_port = self.server.split(':')
        server = server_port[0]
        if len(server_port) > 1:
            port = int(server_port[1])
        else:
            port = 5222
        
        return (server,port)
        
    def register_handlers(self):
        self.client.Dispatcher.RegisterHandler('message',self.xmpp_message)
        self.client.Dispatcher.RegisterDefaultHandler(self.debugging_handler)
        
    def debugging_handler(self, con, event):
        try:
            logging.debug('Event: %s',event)
        except UnicodeEncodeError:
            logging.debug('Event: UnicodeEncodeError Exception')

    def xmpp_message(self, con, event):
        type = event.getType()
        jid_from = event.getFrom().getStripped()

        if jid_from not in self.messages_store:
            self.messages_store[jid_from] = []
        
        message_text = event.getBody()
        if  message_text is not None:
            self.messages_store[jid_from].append({'id':event.getID(),'text':message_text})
        
    def setup_connection(self):         
        if not self.client.isConnected():
            con = self.client.connect(server=self.server_tuple())
            if con is None:
                raise XMPPConnectionError(self.server)
                
            auth = self.client.auth(self.jid.getNode(),self.password,resource = self.jid.getResource())
            if not auth:
                raise XMPPAuthError()
            
            self.register_handlers()
            self.client.sendInitPresence()
            #self.process_thread.start()
            
    def send(self,to_jid,message):
        self.setup_connection()
        if self.client.isConnected():
            id = self.client.send(xmpp.protocol.Message(to_jid,message))
            if not id:
                raise XMPPSendError()
            return id
        else:
            raise XMPPSendError()
            
    def contacts(self):
        if self.client.isConnected():
            roster = self.client.getRoster()
            items = roster.getItems()
            agg_roster = {}
            
            for item in items:
                agg_roster[item] = roster.getItem(item)
                agg_roster[item]['status'] =  roster.getStatus(item)
                agg_roster[item]['priority'] =  roster.getPriority(item)
                
            return agg_roster
        else:
            raise XMPPRosterError()
            
    def contact(self,jid):
        self.client.getRoster().getRoster()
        if self.client.isConnected():
            return self.client.getRoster().getItem(jid)
        else:
            raise XMPPRosterError()
            
    def messages(self,jid):
        try: 
            return self.messages_store[jid]
        except KeyError:
            return []

    def all_messages(self):
        return self.messages_store

    def add_contact(self,jid):
        self.client.getRoster().Subscribe(jid)
        self.client.Process(0.1)

    def remove_contact(self,jid):
        self.client.getRoster().Unauthorize(jid)
        self.client.getRoster().Unsubscribe(jid)
        self.client.getRoster().delItem(jid)

    def authorize_contact(self,jid):
        self.client.getRoster().Authorize(jid)
        self.client.Process(0.1)

    def unauthorize_contact(self,jid):
        self.client.getRoster().Unauthorize(jid)


class XMPPSessionThread(threading.Thread):
    """Threaded XMPP session"""
    def __init__(self, session):
        super(XMPPSessionThread, self).__init__()
        self.session = session
        self.keepRunning = True

    def run(self):
        while self.keepRunning:
            self.session.client.Process(1)

        self.session.clean()

    def stop(self):
        self.keepRunning = False
        

class XMPPSessionPool():
    def __init__(self):
        self.session_pool = {}
        
    def start_session(self,jid,password,server=None):
        session_id = jid
        self.session_pool[session_id] = XMPPSessionThread(XMPPSession(jid,password,server))
        self.session_pool[session_id].start()
        return session_id

    def close_session(self,session_id):
        session = self.session_pool[session_id]
        session.stop()
        session.join(0)
        del self.session_pool[session_id]
        
    def session_for_id(self,session_id):
        return self.session_pool[session_id].session

    def __del__(self):
        for session_key in self.session_pool.keys():
            self.close_session(session_key)


class XMPPPlugin(object):

    name = 'xmpp_pool'
    api = 2

    def __init__(self,keyword = 'xmpp_pool'):
        self.session_pool = XMPPSessionPool()
        self.keyword = keyword

    def setup(self, app):
        ''' Make sure that other installed plugins don't affect the same
            keyword argument.'''
        for other in app.plugins:
            if not isinstance(other, XMPPPlugin): continue
            if other.keyword == self.keyword:
                raise PluginError("Found another sqlite plugin with conflicting settings (non-unique keyword).")

    def apply(self, callback, context):
        # Override global configuration with route-specific values.
        conf = context.config.get('xmpp_pool') or {}
        keyword = conf.get('keyword', self.keyword)

        # Test if the original callback accepts a 'db' keyword.
        # Ignore it if it does not need a database handle.
        args = inspect.getargspec(context.callback)[0]
        if keyword not in args:
            return callback

        def wrapper(*args, **kwargs):
            kwargs[keyword] = self.session_pool

            rv = callback(*args, **kwargs)
            return rv

        # Replace the route callback with the wrapped one.
        return wrapper

    def __del__(self):
        self.session_pool.__del__()

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        