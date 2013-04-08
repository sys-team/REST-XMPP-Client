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