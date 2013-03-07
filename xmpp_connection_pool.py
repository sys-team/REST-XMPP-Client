# -*- coding: utf-8 -*-

import xmpp
import os
import logging
import threading

class XMPPProcessThread(threading.Thread):
    """Threaded XMPP process"""
    def __init__(self, client):
        threading.Thread.__init__(self)
        self.client = client

    def run(self):
        while True:
            self.client.Process(1)

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

class XMPPConnection():
    def __init__(self,jid,password,server=None):
        self.jid = xmpp.protocol.JID(jid)
        if  server is None:
            server = self.jid.getDomain()
        self.password=password
        self.server = server
        self.client = xmpp.Client(self.jid.getDomain(),debug = [])
        self.messages_store = {}
        self.process_thread = XMPPProcessThread(self.client)
        self.client.RegisterDisconnectHandler(self.setup_connection())

    def __del__(self):
        print 'stopping'
        self.process_thread.join(0)
        print self.process_thread.isAlive()
        self.client.UnregisterDisconnectHandler(self.setup_connection())
        
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
            print 'event',event
        except UnicodeEncodeError:
            print 'event','unknown encoding'

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
            self.process_thread.start()
            
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
        self.client.Process(0.5)

    def remove_contact(self,jid):
        self.client.getRoster().Unauthorize(jid)
        self.client.getRoster().Unsubscribe(jid)
        self.client.getRoster().delItem(jid)

    def authorize_contact(self,jid):
        self.client.getRoster().Authorize(jid)
        self.client.Process(0.5)

    def unauthorize_contact(self,jid):
        self.client.getRoster().Unauthorize(jid)
        

class XMPPSessionPool():
    def __init__(self):
        self.session_pool = {}
        
    def start_session(self,jid,password,server=None):
        session_id = jid
        self.session_pool[session_id] = XMPPConnection(jid,password,server)
        self.session_pool[session_id].setup_connection()
        return session_id

    def close_session(self,session_id):
        session = self.session_pool[session_id]
        del self.session_pool[session_id]
        session.__del__()
        
    def session_for_id(self,session_id):
        return self.session_pool[session_id]

    def __del__(self):
        for session_key in self.session_pool.keys():
            self.close_session(session_key)

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        