# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import xmpp
import uuid
import operator
from event_id import XMPPSessionEventID

class XMPPSecureRoster(xmpp.roster.Roster):
    def __init__(self,id_generator):
        xmpp.roster.Roster.__init__(self)
        self.uuid_namespace = uuid.uuid4()
        self._internal_data = {}
        self.default_priority = 0
        self.self_jid = None
        self.id_generator = id_generator

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

    def _new_roster_item(self,jid):
        item_id = self.itemId(jid)
        self._data[item_id] = {'id':item_id,
                                'jid':jid,
                                'name':None,
                                'show':'offline',
                                'status':None,
                                'authorization':'none',
                                'read_offset':0,
                                'subscription':'none',
                                'ask':None,}
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

            if ((item.getAttr('subscription')=='none'
                or item.getAttr('subscription')=='from')
                and item.getAttr('ask') != 'subscribe'): # ignore contacts without any subscriptions
                continue

            if  item.getAttr('ask') == 'subscribe' and stanza.getAttr('type') != 'set': #Resend subscription request
                self.Unsubscribe(jid=jid)
                self.Subscribe(jid=jid)

            self.DEBUG('Setting roster item %s...'%item_id,'ok')
            if item_id not in  self._data:
                self._new_roster_item(jid)
            roster_item = self._data[item_id]
            internal_data_item = self._get_item_internal_data(item_id)
            roster_item['event_id'] = self.id_generator.id()
            roster_item['name'] = item.getAttr('name')
            roster_item['ask'] = item.getAttr('ask')
            roster_item['subscription'] = item.getAttr('subscription')
            if roster_item['subscription'] == 'from' or roster_item['subscription'] == 'both':
                roster_item['authorization'] = 'granted'
            roster_item['groups'] = []
            for group in item.getTags('group'):
                roster_item['groups'].append(group.getData())

            internal_data_item['name'] = item.getAttr('name')

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

        internal_data = self._get_item_internal_data(item_id)
        roster_item_resources = internal_data['resources']
        typ=pres.getType()

        if not typ:
            self.DEBUG('Setting roster item %s for resource %s...'%(jid.getStripped(),jid.getResource()),'ok')
            if jid.getResource() not in roster_item_resources:
                roster_item_resources[jid.getResource()]={'priority':0,'show':'online','status':None,'nick':None}

            res = roster_item_resources[jid.getResource()]

            if pres.getTag('priority'):
                res['priority'] = int(pres.getPriority())
            else:
                res['priority'] = 0

            if pres.getTag('show'):
                res['show'] = pres.getShow()
            else:
                res['show'] = 'online'

            res['status'] = pres.getStatus()
            res['nick'] = pres.getTagData('nick')

        elif typ == 'subscribe':
            roster_item = self._data.get(item_id)
            if roster_item is None:
                roster_item = self._new_roster_item(jid.getStripped())
                roster_item['authorization'] = 'requested'
                roster_item['event_id']=self.id_generator.id()
            else:
                if roster_item['subscription'] == 'to':
                    self.Authorize(roster_item['jid'])

        elif typ == 'subscribed':
            if item_id in self._data:
                self._data[item_id]['authorization'] = 'granted'
                self._data[item_id]['event_id']=self.id_generator.id()

        elif typ == 'unavailable' and jid.getResource() in roster_item_resources:
            del roster_item_resources[jid.getResource()]

        # Need to handle type='error' also

        current_resource = None
        if len(roster_item_resources):
            current_resource = max(roster_item_resources.itervalues(), key=operator.itemgetter('priority'))
        else:
            current_resource = {'priority':0,'show':'offline','status':None,'nick':None}

        if item_id in self._data:
            roster_item = self._data[item_id]
            roster_item['event_id']=self.id_generator.id()
            roster_item['show'] = current_resource['show']
            roster_item['status'] = current_resource['status']
            internal_data['nick'] = current_resource['nick']
            if internal_data['name'] is None:
                if current_resource['nick'] is not None:
                    roster_item['name'] = current_resource['nick']
                else:
                    roster_item['name'] = jid.getStripped()

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

    def setItemReadOffset(self,item_id,read_offset):
        if item_id in self._data and 'read_offset' in self._data[item_id]:
            item = self._data[item_id]
            if  read_offset > item['read_offset']:
                item['read_offset'] = read_offset
                item['event_id'] = self.id_generator.id()

    def getItemReadOffset(self,item_id):
        if item_id in self._data and 'read_offset' in self._data[item_id]:
            return self._data[item_id]['read_offset']
        else:
            return 0

    def getContacts(self,event_offset=None):
        contacts = self.getRawRoster().values()
        if  event_offset is not None:
            contacts = filter(lambda contact: contact['event_id'] > event_offset,contacts)
        return contacts

    def getRawItem(self,jid):
        """ Returns roster item 'jid' representation in internal format. """
        return self._data[self.itemId(jid[:(jid+'/').find('/')])]

    def getResources(self,jid):
        """ Returns list of connected resources of contact 'jid'."""
        return self._internal_data[self.itemId(jid[:(jid+'/').find('/')])]['resources'].keys()

    def getItemByJID(self,jid):
        return self.getItem(self.itemId(jid))

    def setItem(self,jid,name=None,groups=[]):
        """ Creates/renames contact 'jid' and sets the groups list that it now belongs to."""
        iq=xmpp.protocol.Iq('set',xmpp.protocol.NS_ROSTER)
        query=iq.getTag('query')
        attrs={'jid':jid}
        if name: attrs['name']=name
        item=query.setTag('item',attrs)
        for group in groups: item.addChild(node=xmpp.simplexml.Node('group',payload=[group]))
        id = self._owner.send(iq)
        return id

    def updateItem(self,contact_id,name=None,groups=None):
        if contact_id not in self._data:
            return

        contact = self._data[contact_id]

        if  (name is None or name == contact['name']) and groups is None:
            return

        if groups is None:
            groups = contact['groups']

        if name is None:
            name = contact['name']

        return self.setItem(contact['jid'],name=name,groups=groups)
