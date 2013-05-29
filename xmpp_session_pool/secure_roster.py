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
        self._internal_data = {}
        self.default_priority = -128
        self.self_jid = None

    def plugin(self,owner,request=1):
        """ Register presence and subscription trackers in the owner's dispatcher.
        Also request roster from server if the 'request' argument is set.
        Used internally."""
        self._owner.Dispatcher.RegisterHandler('iq',self.RosterIqHandler,'result',xmpp.protocol.NS_ROSTER)
        self._owner.Dispatcher.RegisterHandler('iq',self.RosterIqHandler,'set',xmpp.protocol.NS_ROSTER)
        self._owner.Dispatcher.RegisterHandler('presence',self.PresenceHandler)
        self.self_jid = ''.join([self._owner.User,'@',self._owner.Server])
        self.self_jid = self.self_jid.lower()
        if request: self.Request()

    def itemId(self,jid):
        return uuid.uuid3(self.uuid_namespace,jid.lower().encode('utf8')).hex

    def _apply_roster_item_name(self,item_id):
        if self._internal_data[item_id]['name'] is not None:
            self._data[item_id]['name'] = self._internal_data[item_id]['name']
        elif self._internal_data[item_id]['nick'] is not None:
            self._data[item_id]['name'] = self._internal_data[item_id]['nick']
        else:
            self._data[item_id]['name'] = self._data[item_id]['jid']

    def _get_item_data(self,item_id):
        if item_id not in self._data:
            self._data[item_id]={'name':None,'ask':None,'subscription':'none','groups':['Not in roster'],
                                 'priority':self.default_priority}
        return self._data[item_id]

    def _get_item_internal_data(self,item_id):
        if item_id not in self._internal_data:
            self._internal_data[item_id] = {'name':None,'nick':None,'resources':{}}
        return self._internal_data[item_id]


    def RosterIqHandler(self,dis,stanza):
        """ Subscription tracker. Used internally for setting items state in
            internal roster representation. """
        for item in stanza.getTag('query').getTags('item'):
            jid=item.getAttr('jid')
            item_id = self.itemId(jid)

            if item.getAttr('subscription')=='remove':
                if item_id in self._data: del self._data[item_id]
                if item_id in self._internal_data: del self._internal_data[item_id]
                raise xmpp.protocol.NodeProcessed             # a MUST
            if item.getAttr('subscription')=='none': # ignore contacts without any subscriptions
                continue
            self.DEBUG('Setting roster item %s...'%item_id,'ok')
            roster_item = self._get_item_data(item_id)
            internal_data_item = self._get_item_internal_data(item_id)
            roster_item['id']=item_id
            roster_item['jid']=jid
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

            internal_data_item['name']=item.getAttr('name')
            self._apply_roster_item_name(item_id)

            #self._data[self._owner.User+'@'+self._owner.Server]={'resources':{},'name':None,'ask':None,'subscription':None,'groups':None,}
        self.set=1

        raise xmpp.protocol.NodeProcessed   # a MUST. Otherwise you'll get back an <iq type='error'/>

    def PresenceHandler(self,dis,pres):
        """ Presence tracker. Used internally for setting items' resources state in
            internal roster representation. """
        jid=xmpp.protocol.JID(pres.getFrom())
        item_id = self.itemId(jid.getStripped())

        if  self.self_jid == jid.getStripped():
            self.DEBUG('Presence from own clients')
            return

        item = self._get_item_data(item_id)
        internal_data = self._get_item_internal_data(item_id)
        item_resources = internal_data['resources']
        typ=pres.getType()

        if 'jid' not in item: item['jid'] = jid.getStripped()
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
            if pres.getTag('nick'):
                res['nick']=pres.getTagData('nick')

            if res['priority'] >= item['priority']:
                item['priority'] = res['priority']
                item['show'] = res['show']
                item['status'] = res['status']
                internal_data['nick'] = res['nick']

        elif typ=='unavailable' and jid.getResource() in item_resources:
            del item_resources[jid.getResource()]
            if len(item_resources):
                res = max(item_resources.itervalues(), key=operator.itemgetter('priority'))
                item['priority'] = res['priority']
                item['show'] = res['show']
                item['status'] = res['status']
                internal_data['nick'] = res['nick']
            else:
                item['priority'] = self.default_priority
                item['show'] = 'offline'
                item['status'] = None
                # Need to handle type='error' also

        self._apply_roster_item_name(item_id)

    def _getItemData(self,jid,dataname):
        """ Return specific jid's representation in internal format. Used internally. """
        jid=jid[:(jid+'/').find('/')]
        return self._data[self.itemId(jid)][dataname]

    def _getResourceData(self,jid,dataname):
        """ Return specific jid's resource representation in internal format. Used internally. """
        if jid.find('/')+1:
            jid,resource=jid.split('/',1)
            item_id = self.itemId(jid)
            if resource in self._internal_data[item_id]['resources']:
                return self._internal_data[item_id]['resources'][resource][dataname]
        elif self._internal_data[self.itemId(jid)]['resources'].keys():
            item_id = self.itemId(jid)
            lastpri=-129
            for r in self._internal_data[item_id]['resources'].keys():
                if int(self._internal_data[item_id]['resources'][r]['priority'])>lastpri: resource,lastpri=r,int(self._internal_data[item_id]['resources'][r]['priority'])
            return self._internal_data[item_id]['resources'][resource][dataname]

    def getRawItem(self,jid):
        """ Returns roster item 'jid' representation in internal format. """
        return self._data[self.itemId(jid[:(jid+'/').find('/')])]

    def getResources(self,jid):
        """ Returns list of connected resources of contact 'jid'."""
        return self._internal_data[self.itemId(jid[:(jid+'/').find('/')])]['resources'].keys()

    def getItemByJID(self,jid):
        return self.getItem(self.itemId(jid))

    def setItem(self,contact_id,name=None,groups=None):
        """Renames contact and sets the groups list that it now belongs to."""
        if not contact_id in self._data:
            return

        contact = self._data[contact_id]
        iq=xmpp.protocol.Iq('set',xmpp.protocol.NS_ROSTER)
        query=iq.getTag('query')
        attrs={'jid':contact['jid']}
        if name:
            attrs['name']=name
            contact['name'] = name
        item=query.setTag('item',attrs)

        if groups is None:
            groups = contact['groups']
        else:
            contact['groups'] = groups

        for group in groups:
            item.addChild(node=xmpp.protocol.Node('group',payload=[group]))
        self._owner.send(iq)