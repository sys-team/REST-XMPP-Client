# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import xmpp
from secure_roster import XMPPSecureRoster

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