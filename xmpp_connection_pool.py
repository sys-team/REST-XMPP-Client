import xmpp
import os
import logging

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
        self.client.Dispatcher.RegisterDefaultHandler(self.dummy_handler)
        
    def dummy_handler(self, con, event):
        print 'event',event

    def xmpp_message(self, con, event):
        type = event.getType()
        jid_from = event.getFrom().getStripped()
        
        print 'message'
        if jid_from not in self.messages_store:
            self.messages_store[jid_from] = []
        
        message_text = event.getBody()
        if  message_text is not None:
            self.messages_store[jid_from].append(message_text)  
        
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
            
    def send(self,to_jid,message):
        self.setup_connection()
        if self.client.isConnected():
            id = self.client.send(xmpp.protocol.Message(to_jid,message))
            if not id:
                raise XMPPSendError()
        else:
            raise XMPPSendError()
            
    def contacts(self):
        if self.client.isConnected():
            self.client.Process(0)
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
        self.client.Process(0)
        self.client.getRoster().getRoster()
        if self.client.isConnected():
            return self.client.getRoster().getItem(jid)
        else:
            raise XMPPRosterError()
            
    def messages(self,jid):
        self.client.Process(0)
        try: 
            return self.messages_store[jid]
        except KeyError:
            return []
        

class XMPPSessionPool():
    def __init__(self):
        self.session_pool = {}
        
    def start_session(self,jid,password,server=None):
        session_id = jid
        self.session_pool[session_id] = XMPPConnection(jid,password,server)
        self.session_pool[session_id].setup_connection()
        return session_id
        
    def session_for_id(self,session_id):
        return self.session_pool[session_id]
    
    
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        