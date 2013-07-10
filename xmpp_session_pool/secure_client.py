# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import xmpp
import socket
import logging
from secure_roster import XMPPSecureRoster
from event_id import XMPPSessionEventID
from errors import XMPPAuthError, XMPPConnectionError, XMPPRosterError, XMPPSendError

class XMPPSecureClient(xmpp.Client):
    def __init__(self,jid,password,server,port=5222):
        self.jid = xmpp.protocol.JID(jid)
        self._Password = password
        self._User = self.jid.getNode()
        self._Resource = self.jid.getResource()
        self._Server = (server,port)
        self.Namespace,self.DBG='jabber:client',xmpp.client.DBG_CLIENT
        xmpp.Client.__init__(self,self.jid.getDomain(),port,debug=[]) #['always', 'nodebuilder']
        self.id_generator = XMPPSessionEventID()

    def reconnectAndReauth(self):
        """ Example of reconnection method. In fact, it can be used to batch connection and auth as well. """
        handlerssave=self.Dispatcher.dumpHandlers()
        defaulHandler = self.Dispatcher._defaultHandler
        if self.__dict__.has_key('ComponentBind'): self.ComponentBind.PlugOut()
        if self.__dict__.has_key('Bind'): self.Bind.PlugOut()
        self._route=0
        if self.__dict__.has_key('NonSASL'): self.NonSASL.PlugOut()
        if self.__dict__.has_key('SASL'): self.SASL.PlugOut()
        if self.__dict__.has_key('TLS'): self.TLS.PlugOut()
        self.Dispatcher.PlugOut()
        if self.__dict__.has_key('HTTPPROXYsocket'): self.HTTPPROXYsocket.PlugOut()
        if self.__dict__.has_key('TCPsocket'): self.TCPsocket.PlugOut()
        if not self.connect(server=self._Server,proxy=self._Proxy): return
        if not self.auth(self._User,self._Password,self._Resource): return
        self.Dispatcher.restoreHandlers(handlerssave)
        self.Dispatcher.RegisterDefaultHandler(defaulHandler)
        return self.connected

    def DisconnectHandler(self):
        while not self.isConnected():
            self.reconnectAndReauth()
        self.sendInitPresence()
        self.getRoster()

    def getRoster(self):
        """ Return the Roster instance, previously plugging it in and
            requesting roster from server if needed. """
        if not self.__dict__.has_key('Roster'):
            XMPPSecureRoster(self.id_generator).PlugIn(self)
        return self.Roster.getRoster()

    def sendPresence(self,jid=None,typ=None,requestRoster=0):
        """ Send some specific presence state.
            Can also request roster from server if according agrument is set."""
        if requestRoster: XMPPSecureRoster(self.id_generator).PlugIn(self)
        self.send(xmpp.dispatcher.Presence(to=jid, typ=typ))

    def setup_connection(self):
        if not self.isConnected():
            logging.debug('SessionEvent : Session %s Setup connection',self.jid)
            print(self._Server)
            con = self.connect(server=self._Server)

            if not self.isConnected() or con is None:
                raise XMPPConnectionError(self.Server)

            auth = self.auth(self._User,self._Password,self._Resource)
            if not auth:
                raise XMPPAuthError()

            self.register_handlers()
            self.sendInitPresence()
            self.getRoster()

    def disconnect(self):
        self.UnregisterDisconnectHandler(self.DisconnectHandler)
        self.Dispatcher.disconnect()

        if 'TCPsocket' in self.__dict__:
            sock = self.__dict__['TCPsocket']
            try:
                sock._sock.shutdown(socket.SHUT_RDWR)
            except:
                logging.debug(u'SessionEvent : Session %s socket shutdowned', self._User)
            sock._sock.close()
            sock.PlugOut()

    def register_handlers(self):
        self.Dispatcher.RegisterHandler('presence',self.xmpp_presence)
        self.Dispatcher.RegisterHandler('iq',self.xmpp_presence)
        #self.Dispatcher.RegisterHandler('message',self.xmpp_message)
        self.Dispatcher.RegisterDefaultHandler(self.debugging_handler)

    def debugging_handler(self, con, event):
        logging.debug(u'XMPPEvent : %s ',event)

    def xmpp_presence(self, con, event):
        #self.poll_notifier.notify()
        pass

    def xmpp_message(self, con, event):
        pass