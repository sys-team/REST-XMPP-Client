# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import xmpp
import uuid
import time
import operator

class XMPPSecureRoster(xmpp.roster.Roster):
    def __init__(self):
        xmpp.roster.Roster.__init__(self)
        self.uuid_namespace = uuid.uuid4()
        self._resources = {}
        self.default_priority = -128

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
            if item.getAttr('subscription')=='none': # ignore contacts without any subscriptions
                continue
            self.DEBUG('Setting roster item %s...'%item_id,'ok')
            if not self._data.has_key(item_id): self._data[item_id]={}
            roster_item = self._data[item_id]
            roster_item['id']=item_id
            roster_item['jid']=jid
            if item.getAttr('name') is not None:
                roster_item['name']=item.getAttr('name')
            else:
                roster_item['name']=jid
            roster_item['ask']=item.getAttr('ask')
            roster_item['subscription']=item.getAttr('subscription')
            roster_item['timestamp']=time.time()
            if not roster_item.has_key('show'):
                roster_item['show']='offline'
            if not roster_item.has_key('status'):
                roster_item['status']=None
            if not roster_item.has_key('priority'):
                roster_item['priority']=self.default_priority
            roster_item['groups']=[]
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

        if not self._data.has_key(item_id): self._data[item_id]={'jid':jid.getStripped(),'name':jid.getStripped(),'ask':None,'subscription':'none','groups':['Not in roster'],'priority':self.default_priority}
        if not self._resources.has_key(item_id): self._resources[item_id] = {}

        item=self._data[item_id]
        item_resources = self._resources[item_id]
        typ=pres.getType()

        item['timestamp'] = time.time()
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

            if pres.getTag('nick'):
                res['nick']=pres.getTagData('nick')
                if res['nick'] is not None:
                    item['name'] = res['nick']


        elif typ=='unavailable' and item_resources.has_key(jid.getResource()):
            del item_resources[jid.getResource()]
            if len(item_resources):
                res = max(item_resources.itervalues(), key=operator.itemgetter('priority'))
                item['priority'] = res['priority']
                item['show'] = res['show']
                item['status'] = res['status']
                if res['nick'] is not None:
                    item['name'] = res['nick']
            else:
                item['priority'] = self.default_priority
                item['show'] = 'offline'
                item['status'] = None
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
        elif self._data[self.itemId(jid)]['resources'].keys():
            item_id = self.itemId(jid)
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