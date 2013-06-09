__author__ = 'kovtash'

import itertools

class XMPPSessionEventID(object):
    def __init__(self):
        self.id = itertools.count().next