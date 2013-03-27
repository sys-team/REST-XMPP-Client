# -*- coding: utf-8 -*-

__author__ = 'kovtash'

import xmpp
import logging
import threading
import inspect
import socket
import uuid
import time
import operator

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

class XMPPSecureRoster(xmpp.roster.Roster):
    def __init__(self):
        xmpp.roster.Roster.__init__(self)
        self.uuid_namespace = uuid.uuid4()
        self._resources = {}

    def plugin(self,owner,request=1):
        """ Register presence and subscription trackers in the owner's dispatcher.
        Also request roster from server if the 'request' argument is set.
        Used internally."""
        self._owner.Dispatcher.RegisterHandler('iq',self.RosterIqHandler,'result',xmpp.protocol.NS_ROSTER)
        self._owner.Dispatcher.RegisterHandler('iq',self.RosterIqHandler,'set',xmpp.protocol.NS_ROSTER)
        self._owner.Dispatcher.RegisterHandler('presence',self.PresenceHandler)
        if request: self.Request()

    def itemId(self,jid):
        return uuid.uuid3(self.uuid_namespace,jid.lower().encode('utf8')).hex

    def RosterIqHandler(self,dis,stanza):
        """ Subscription tracker. Used internally for setting items state in
            internal roster representation. """
        for item in stanza.getTag('query').getTags('item'):
            jid=item.getAttr('jid')
            item_id = self.itemId(jid)

            if item.getAttr('subscription')=='remove':
                if self._data.has_key(item_id): del self._data[item_id]
                raise xmpp.protocol.NodeProcessed             # a MUST
            self.DEBUG('Setting roster item %s...'%item_id,'ok')
            if not self._data.has_key(item_id): self._data[item_id]={}
            roster_item = self._data[item_id]
            roster_item['id']=item_id
            roster_item['jid']=jid
            roster_item['name']=item.getAttr('name')
            roster_item['ask']=item.getAttr('ask')
            roster_item['subscription']=item.getAttr('subscription')
            roster_item['groups']=[]
            roster_item['timestamp']=time.time()
            if not roster_item.has_key('show'):
                roster_item['show']='offline'
            if not roster_item.has_key('status'):
                roster_item['status']=None
            if not roster_item.has_key('priority'):
                roster_item['priority']=-128
            for group in item.getTags('group'):
                roster_item['groups'].append(group.getData())
        #self._data[self._owner.User+'@'+self._owner.Server]={'resources':{},'name':None,'ask':None,'subscription':None,'groups':None,}
        self.set=1
        raise xmpp.protocol.NodeProcessed   # a MUST. Otherwise you'll get back an <iq type='error'/>

    def PresenceHandler(self,dis,pres):
        """ Presence tracker. Used internally for setting items' resources state in
            internal roster representation. """
        jid=xmpp.protocol.JID(pres.getFrom())
        item_id = self.itemId(jid.getStripped())

        self_jid = self._owner.User+'@'+self._owner.Server
        self_jid = self_jid.lower()
        if  self_jid == jid.getStripped():
            self.DEBUG('Presence from own clients')
            return

        if not self._data.has_key(item_id): self._data[item_id]={'jid':jid.getStripped(),'name':None,'ask':None,'subscription':'none','groups':['Not in roster'],'priority':0}
        if not self._resources.has_key(item_id): self._resources[item_id] = {}

        item=self._data[item_id]
        item_resources = self._resources[item_id]
        typ=pres.getType()

        if not typ:
            self.DEBUG('Setting roster item %s for resource %s...'%(jid.getStripped(),jid.getResource()),'ok')
            item_resources[jid.getResource()]=res={'show':'online','status':None,'priority':0,'nick':None}

            if pres.getTag('priority'):
                res['priority']=int(pres.getPriority())
            if pres.getTag('show'):
                res['show']=pres.getShow()
            if pres.getTag('status'):
                res['status']=pres.getStatus()

            if res['priority'] >= item['priority']:
                item['priority'] = res['priority']
                item['show'] = res['show']
                item['status'] = res['status']
                item['timestamp'] = time.time()

            if pres.getTag('nick'):
                res['nick']=pres.getTagData('nick')
                if item['name'] is None and res['nick'] is not None:
                    item['name'] = res['nick']
                    item['timestamp'] = time.time()


        elif typ=='unavailable' and item_resources.has_key(jid.getResource()):
            del item_resources[jid.getResource()]
            if len(item_resources):
                res = max(item_resources.iteritems(), key=operator.itemgetter(1))[0]
                item['priority'] = res['priority']
                item['show'] = res['show']
                item['status'] = res['status']
                item['timestamp'] = time.time()
            else:
                item['priority'] = -128
                item['show'] = 'offline'
                item['status'] = None
                item['timestamp'] = time.time()
        # Need to handle type='error' also

    def _getItemData(self,jid,dataname):
        """ Return specific jid's representation in internal format. Used internally. """
        jid=jid[:(jid+'/').find('/')]
        return self._data[self.itemId(jid)][dataname]

    def _getResourceData(self,jid,dataname):
        """ Return specific jid's resource representation in internal format. Used internally. """
        if jid.find('/')+1:
            jid,resource=jid.split('/',1)
            item_id = self.itemId(jid)
            if self._data[item_id]['resources'].has_key(resource): return self._data[item_id]['resources'][resource][dataname]
        elif self._data[item_id]['resources'].keys():
            lastpri=-129
            for r in self._data[item_id]['resources'].keys():
                if int(self._data[item_id]['resources'][r]['priority'])>lastpri: resource,lastpri=r,int(self._data[item_id]['resources'][r]['priority'])
            return self._data[item_id]['resources'][resource][dataname]

    def getRawItem(self,jid):
        """ Returns roster item 'jid' representation in internal format. """
        return self._data[self.itemId(jid[:(jid+'/').find('/')])]

    def getResources(self,jid):
        """ Returns list of connected resources of contact 'jid'."""
        return self._data[self.itemId(jid[:(jid+'/').find('/')])]['resources'].keys()

    def getItemByJID(self,jid):
        return self.getItem(self.itemId(jid))

class XMPPSecureClient(xmpp.Client):
    def __init__(self,server,port=5222,debug=['always', 'nodebuilder']):
        self.Namespace,self.DBG='jabber:client',xmpp.client.DBG_CLIENT
        xmpp.Client.__init__(self,server,port,debug)

    def getRoster(self):
        """ Return the Roster instance, previously plugging it in and
            requesting roster from server if needed. """
        if not self.__dict__.has_key('Roster'): XMPPSecureRoster().PlugIn(self)
        return self.Roster.getRoster()

    def sendPresence(self,jid=None,typ=None,requestRoster=0):
        """ Send some specific presence state.
            Can also request roster from server if according agrument is set."""
        if requestRoster: XMPPSecureRoster().PlugIn(self)
        self.send(xmpp.dispatcher.Presence(to=jid, typ=typ))

class XMPPNotificationPoller():
    def __init__(self,timeout=60,poll_interval=1):
        self.is_notification_available = False
        self.timeout = timeout
        self.poll_interval = poll_interval

    def run(self):
        while not self.is_notification_available:
            self.timeout -= self.poll_interval
            if  self.timeout < 0:
                return False

            time.sleep(self.poll_interval)
        return True

    def notify(self):
        self.is_notification_available = True

class XMPPSession():
    def __init__(self,jid,password,server=None,max_message_size = 512, chat_buffer_size=50):
        self.token = uuid.uuid4().hex
        self.jid = xmpp.protocol.JID(jid)
        if  server is None:
            server = self.jid.getDomain()
        self.password=password
        self.server = server
        self.max_message_size = max_message_size
        self.chat_buffer_size = chat_buffer_size
        #self.client = xmpp.Client(self.jid.getDomain(),debug = [])
        self.client = XMPPSecureClient(self.jid.getDomain(),debug = [])
        self.chats_store = {}
        self.client.RegisterDisconnectHandler(self.client.reconnectAndReauth)
        self.client.UnregisterDisconnectHandler(self.client.DisconnectHandler)
        self.setup_connection()
        self.poller_pool = []

    def clean(self):
        logging.info('Session %s start cleaning', self.jid)
        self.client.UnregisterDisconnectHandler(self.client.reconnectAndReauth)
        self.client.Dispatcher.disconnect()
        self.send_notification()

        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']
            try:
                sock._sock.shutdown(socket.SHUT_RDWR)
            except:
                logging.info('Session %s socket shutdowned', self.jid)
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


    def append_message(self,jid,inbound,id,text):
        if jid not in self.chats_store:
            self.chats_store[jid] = []

        messages = []

        for i in xrange(0, len(text), self.max_message_size):
            messages.append({'id':id,
                             'inbound':inbound,
                             'text':text[i:i+self.max_message_size],
                             'time-stamp':time.time()
            })

        for message in messages:
            self.chats_store[jid].append(message)

        if len(self.chats_store[jid]) > self.chat_buffer_size:
            for i in xrange (0,len(self.chats_store[jid])-self.chat_buffer_size):
                self.chats_store[jid].pop(0)

        return messages

    def xmpp_message(self, con, event):
        type = event.getType()
        jid_from = event.getFrom().getStripped()

        message_text = event.getBody()
        if  message_text is not None:
            self.append_message(jid=jid_from,inbound=True,id=event.getID(),text=message_text)
            self.send_notification()
        
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
            self.client.getRoster()
            self.client.Dispatcher.Process(5)
            
    def send(self,contact_id,message):
        jid = self.client.getRoster().getItem(contact_id)['jid']
        return self.sendByJID(jid,message)

    def sendByJID(self,jid,message):
        self.setup_connection()
        if self.client.isConnected():
            id = self.client.send(xmpp.protocol.Message(jid,message))
            if not id:
                raise XMPPSendError()

            return self.append_message(jid=jid,inbound=False,id=id,text=message)
        else:
            raise XMPPSendError()

            
    def contacts(self,from_timestamp=None):
        if not self.client.isConnected():
            raise XMPPRosterError()

        raw_roster = self.client.getRoster().getRawRoster()
        return raw_roster.values()

            
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
            
    def messages(self,contact_id):
        try:
            jid = self.client.getRoster().getItem(contact_id)['jid']
            return self.chats_store[jid]
        except KeyError:
            return []

    def all_messages(self):
        return self.chats_store

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

    def send_notification(self):
        for poller in self.poller_pool:
            poller.notify()

    def poll_changes(self):
        poller = XMPPNotificationPoller()
        self.poller_pool.append(poller)
        result = poller.run()
        self.poller_pool.remove(poller)
        return result


class XMPPSessionThread(threading.Thread):
    """Threaded XMPP session"""
    def __init__(self, session):
        super(XMPPSessionThread, self).__init__()
        self.session = session
        self.keepRunning = True

    def run(self):
        while self.keepRunning:
            self.session.client.Process(1)
            time.sleep(1)

        self.session.clean()

    def stop(self):
        self.keepRunning = False
        

class XMPPSessionPool():
    def __init__(self,debug=False):
        self.session_pool = {}
        self.debug = debug
        
    def start_session(self,jid,password,server=None):
        if  self.debug:
            session_id = jid
        else:
            session_id = uuid.uuid4().hex
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

    def __init__(self,keyword = 'xmpp_pool',debug=False):
        self.session_pool = XMPPSessionPool(debug=debug)
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