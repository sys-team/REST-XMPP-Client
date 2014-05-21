# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import xmpp
import uuid
import operator
from event_id import XMPPSessionEventID

NS_MUC = 'http://jabber.org/protocol/muc'
NS_MUC_USER = "http://jabber.org/protocol/muc#user"

class XMPPRoster(xmpp.roster.Roster):
    def __init__(self, id_generator):
        xmpp.roster.Roster.__init__(self)
        self.uuid_namespace = uuid.uuid4()
        self._internal_data = {}
        self.default_priority = 0
        self.self_jid = None
        self.id_generator = id_generator
        self._jid_to_id_mapping = {}
        self._muc_list = {}
        self._muc_members = {}

    def plugin(self, owner, request=1):
        """ Register presence and subscription trackers in the owner's dispatcher.
        Also request roster from server if the 'request' argument is set.
        Used internally."""
        self._owner.Dispatcher.RegisterHandler('iq', self.RosterIqHandler, 'result',
                                               xmpp.protocol.NS_ROSTER, makefirst=True)
        self._owner.Dispatcher.RegisterHandler('iq', self.RosterIqHandler, 'set',
                                               xmpp.protocol.NS_ROSTER, makefirst=True)
        self._owner.Dispatcher.RegisterHandler('presence', self.PresenceHandler, makefirst=True)
        self._owner.Dispatcher.RegisterHandler('message', self.muc_invite_handler, 'normal', makefirst=True)
        self.self_jid = ''.join([self._owner.User, '@', self._owner.Server])
        self.self_jid = self.self_jid.lower()
        if request:
            self.Request()

    def itemId(self, jid):
        contact_id = self._jid_to_id_mapping.get(jid, None)
        if contact_id is None:
            contact_id = uuid.uuid3(self.uuid_namespace,jid.lower().encode('utf8')).hex
            self._jid_to_id_mapping[jid] = contact_id
        return contact_id

    def _new_roster_item(self, jid):
        item_id = self.itemId(jid)
        self._data[item_id] = {'id': item_id,
                               'jid': jid,
                               'name': None,
                               'show': 'offline',
                               'status': None,
                               'authorization': 'none',
                               'read_offset': 0,
                               'subscription': 'none',
                               'ask': None}
        return self._data[item_id]

    def _new_muc_roster_item(self, jid):
        item_id = self.itemId(jid)
        self._muc_list[item_id] = {'id': item_id,
                                   'jid': jid,
                                   'name': None,
                                   'read_offset': 0}
        self._muc_members[item_id] = {}

    def _get_item_internal_data(self, item_id):
        if item_id not in self._internal_data:
            self._internal_data[item_id] = {'name': None, 'nick': None, 'resources': {}}
        return self._internal_data[item_id]

    def get_muc(self, muc_id):
        result = None
        if muc_id in self._muc_list:
            result = self._muc_list[muc_id].copy()
            result['members'] = []
            if muc_id in self._muc_members:
                result['members'] = self._muc_members[muc_id].values()
        return result

    def get_muc_by_jid(self, muc_jid):
        return self.get_muc(self.itemId(muc_jid.getStripped()))

    def muc_invite_handler(self, dis, message):
        for item in message.getTags('x'):
            if item.getAttr('xmlns') == NS_MUC_USER:
                invited_by_jid = item.getTag('invite').getAttr('from')
                invited_by_jid = invited_by_jid.split('/')[0]
                muc_jid = message.getFrom()
                if self.getItemByJID(invited_by_jid) is not None and muc_jid is not None:
                    self.join_muc_by_jid(muc_jid)

    def muc_user_handler(self, dis, pres):
        print(pres)

        muc_jid = xmpp.protocol.JID(pres.getFrom())
        item_id = self.itemId(muc_jid.getStripped())
        member_id = muc_jid.getResource()

        pres_muc_user = pres.getTag('x', namespace=NS_MUC_USER)
        pres_item = pres_muc_user.getTag('item')
        muc_user_jid = xmpp.JID(pres_item.getAttr('jid'))

        typ = pres.getType()

        if typ is None:
            if item_id not in self._muc_list:
                self._new_muc_roster_item(muc_jid.getStripped())

            muc = self._muc_list[item_id]
            muc['event_id'] = self.id_generator.id()

            if muc_user_jid.getStripped() != self._owner.jid.getStripped():
                member_contact_id = self.itemId(muc_user_jid.getStripped())
                if member_contact_id not in self._data:
                    member_contact_id = None

                muc_members = self._muc_members[item_id]
                muc_members[member_id] = {'jid': muc_user_jid.getStripped(),
                                          'member_id': member_id,
                                          'contact_id': member_contact_id,
                                          'name': member_id}

        elif typ == 'unavailable':
            if self._owner.jid.getStripped() == muc_user_jid.getStripped():
                del self._muc_members[item_id]
                del self._muc_list[item_id]
            else:
                if item_id in self._muc_members:
                    muc_members = self._muc_members[item_id]
                    del muc_members[member_id]

                    if item_id in self._muc_list:
                        muc = self._muc_list[item_id]
                        muc['event_id'] = self.id_generator.id()

    def RosterIqHandler(self, dis, stanza):
        """ Subscription tracker. Used internally for setting items state in
            internal roster representation. """
        for item in stanza.getTag('query').getTags('item'):
            jid = item.getAttr('jid')
            item_id = self.itemId(jid)

            if item.getAttr('subscription') == 'remove':
                if item_id in self._data:
                    del self._data[item_id]
                if item_id in self._internal_data:
                    del self._internal_data[item_id]
                raise xmpp.protocol.NodeProcessed  # a MUST

            if ((item.getAttr('subscription') == 'none'
                or item.getAttr('subscription') == 'from')
                and item.getAttr('ask') != 'subscribe'):  # Ignore contacts without any subscriptions
                continue

            if item.getAttr('ask') == 'subscribe' and stanza.getAttr('type') != 'set':  # Resend subscription request
                self.Unsubscribe(jid=jid)
                self.Subscribe(jid=jid)

            self.DEBUG('Setting roster item %s...' % item_id, 'ok')
            if item_id not in self._data:
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

        self.set = 1

        raise xmpp.protocol.NodeProcessed   # a MUST. Otherwise you'll get back an <iq type='error'/>

    def PresenceHandler(self, dis, pres):
        """ Presence tracker. Used internally for setting items' resources state in
            internal roster representation. """

        jid = xmpp.protocol.JID(pres.getFrom())
        item_id = self.itemId(jid.getStripped())

        if pres.getTag('x', namespace=NS_MUC_USER) is not None:
            self.muc_user_handler(dis, pres)
            return  # MUC should not be processed here

        if self.self_jid == jid.getStripped():
            self.DEBUG('Presence from own clients')
            return

        internal_data = self._get_item_internal_data(item_id)
        roster_item_resources = internal_data['resources']
        typ = pres.getType()

        if not typ:
            self.DEBUG('Setting roster item %s for resource %s...' % (jid.getStripped(), jid.getResource()), 'ok')
            if jid.getResource() not in roster_item_resources:
                roster_item_resources[jid.getResource()] = {'priority': 0, 'show': 'online',
                                                            'status': None, 'nick': None}

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
                roster_item['event_id'] = self.id_generator.id()
            else:
                if roster_item['subscription'] == 'to':
                    self.Authorize(roster_item['jid'])

        elif typ == 'subscribed':
            if item_id in self._data:
                self._data[item_id]['authorization'] = 'granted'
                self._data[item_id]['event_id'] = self.id_generator.id()

        elif typ == 'unavailable' and jid.getResource() in roster_item_resources:
            del roster_item_resources[jid.getResource()]

        # Need to handle type='error' also

        current_resource = None
        if len(roster_item_resources):
            current_resource = max(roster_item_resources.itervalues(), key=operator.itemgetter('priority'))
        else:
            current_resource = {'priority': 0, 'show': 'offline', 'status': None, 'nick': None}

        if item_id in self._data:
            roster_item = self._data[item_id]
            roster_item['event_id'] = self.id_generator.id()
            roster_item['show'] = current_resource['show']
            roster_item['status'] = current_resource['status']
            internal_data['nick'] = current_resource['nick']
            if internal_data['name'] is None:
                if current_resource['nick'] is not None:
                    roster_item['name'] = current_resource['nick']
                else:
                    roster_item['name'] = jid.getStripped()

    def _getItemData(self, jid, dataname):
        """ Return specific jid's representation in internal format. Used internally. """
        jid = jid[:(jid+'/').find('/')]
        return self._data[self.itemId(jid)][dataname]

    def _getResourceData(self, jid, dataname):
        """ Return specific jid's resource representation in internal format. Used internally. """
        if jid.find('/') + 1:
            jid, resource = jid.split('/', 1)
            item_id = self.itemId(jid)
            if resource in self._internal_data[item_id]['resources']:
                return self._internal_data[item_id]['resources'][resource][dataname]
        elif self._internal_data[self.itemId(jid)]['resources'].keys():
            item_id = self.itemId(jid)
            lastpri =- 129
            for r in self._internal_data[item_id]['resources'].keys():
                if int(self._internal_data[item_id]['resources'][r]['priority']) > lastpri: resource, lastpri=r, int(self._internal_data[item_id]['resources'][r]['priority'])
            return self._internal_data[item_id]['resources'][resource][dataname]

    def setItemReadOffset(self, item_id, read_offset):
        if item_id not in self._data:
            return False

        item = self._data[item_id]
        if 'read_offset' not in item or read_offset > item['read_offset']:
            item['read_offset'] = read_offset
            item['event_id'] = self.id_generator.id()
            return True

        return False

    def getItemReadOffset(self, item_id):
        if item_id in self._data and 'read_offset' in self._data[item_id]:
            return self._data[item_id]['read_offset']

        return 0

    def setItemHistoryOffset(self, item_id, history_offset):
        if item_id not in self._data:
            return False

        item = self._data[item_id]
        if 'history_offset' not in item or history_offset > item['history_offset']:
            item['history_offset'] = history_offset
            item['event_id'] = self.id_generator.id()
            return True

        return False

    def getItemHistoryOffset(self, item_id):
        if item_id in self._data and 'history_offset' in self._data[item_id]:
            return self._data[item_id]['history_offset']

        return 0

    def getContacts(self, event_offset=None):
        contacts = self.getRawRoster().values()
        if event_offset is not None:
            contacts = filter(lambda contact: contact['event_id'] > event_offset, contacts)
        return contacts

    def getRawItem(self, jid):
        """ Returns roster item 'jid' representation in internal format. """
        return self._data[self.itemId(jid[:(jid+'/').find('/')])]

    def getResources(self, jid):
        """ Returns list of connected resources of contact 'jid'."""
        return self._internal_data[self.itemId(jid[:(jid+'/').find('/')])]['resources'].keys()

    def getItemByJID(self, jid):
        return self.getItem(self.itemId(jid))

    def setItem(self, jid, name=None, groups=[]):
        """ Creates/renames contact 'jid' and sets the groups list that it now belongs to."""
        iq = xmpp.protocol.Iq('set', xmpp.protocol.NS_ROSTER)
        query = iq.getTag('query')
        attrs = {'jid': jid}
        if name:
            attrs['name'] = name
        item = query.setTag('item', attrs)
        for group in groups:
            item.addChild(node=xmpp.simplexml.Node('group', payload=[group]))
        return self._owner.send(iq)

    def updateItem(self, contact_id, name=None, groups=None):
        if contact_id not in self._data:
            return

        contact = self._data[contact_id]

        if (name is None or name == contact['name']) and groups is None:
            return

        if groups is None:
            groups = contact['groups']

        if name is None:
            name = contact['name']

        return self.setItem(contact['jid'], name=name, groups=groups)

    def muc_jid_by_id(self, muc_id):
        if muc_id in self._muc_list:
            return xmpp.JID(self._muc_list[muc_id]['jid'])

        return None

    def item_jid_by_id(self, contact_id):
        if contact_id in self._data:
            return xmpp.JID(self._data[contact_id]['jid'])

        return None

    def join_muc_by_jid(self, muc_jid):
        user_muc_jid = xmpp.protocol.JID(node=muc_jid.node, domain=muc_jid.domain,
                                         resource=self._owner.muc_member_id)
        muc = xmpp.protocol.Protocol(name='x', xmlns=NS_MUC)
        pres = xmpp.protocol.Presence(to=user_muc_jid, payload=[muc])
        return self._owner.send(pres)

    def leave_muc_by_jid(self, muc_jid):
        user_muc_jid = xmpp.protocol.JID(node=muc_jid.node, domain=muc_jid.domain,
                                         resource=self._owner.muc_member_id)
        pres = xmpp.protocol.Presence(to=user_muc_jid, typ='unavailable')
        return self._owner.send(pres)

    def leave_muc(self, muc_id):
        muc_jid = self.muc_jid_by_id(muc_id)
        return self.leave_muc_by_jid(muc_jid)

    def invite_to_muc_by_jid(self, muc_jid, member_jid):
        invite = xmpp.protocol.Protocol(name='invite', to=member_jid.getStripped())
        x = xmpp.protocol.Protocol(name='x', xmlns='http://jabber.org/protocol/muc#user', payload=[invite])
        invite_message = xmpp.protocol.Message(to=muc_jid, payload=[x])
        return self._owner.send(invite_message)

    def invite_to_muc(self, muc_id, contact_id):
        muc_jid = self.muc_jid_by_id(muc_id)
        contact_jid = self.item_jid_by_id(contact_id)
        return self.invite_to_muc_by_jid(muc_jid, contact_jid)

    def set_muc_read_offset(self, muc_id, read_offset):
        if muc_id in self._muc_list:
            muc = self._muc_list[muc_id]
            if 'read_offset' not in self._muc_list[muc_id] or read_offset > muc['read_offset']:
                muc['read_offset'] = read_offset
                muc['event_id'] = self.id_generator.id()
                return True
        return False

    def get_muc_read_offset(self, muc_id):
        if muc_id in self._muc_list and 'read_offset' in self._muc_list[muc_id]:
            return self._muc_list[muc_id]['read_offset']

        return 0

    def set_muc_history_offset(self, muc_id, history_offset):
        if muc_id not in self._muc_list:
            return False

        muc = self._muc_list[muc_id]
        if 'history_offset' not in muc or history_offset > muc['history_offset']:
            muc['history_offset'] = history_offset
            muc['event_id'] = self.id_generator.id()
            return True

        return False

    def get_muc_history_offset(self, muc_id):
        if muc_id in self._muc_list and 'history_offset' in self._muc_list[muc_id]:
            return self._muc_list[muc_id]['history_offset']

        return 0

    def get_mucs(self, event_offset=None):
        mucs = self._muc_list.values()
        if event_offset is not None:
            mucs = filter(lambda muc: muc['event_id'] > event_offset, mucs)
        return mucs

    def get_contacts_and_mucs(self, event_offset=None):
        return self.getContacts(event_offset=event_offset) + self.get_mucs(event_offset=event_offset)
