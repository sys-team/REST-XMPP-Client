__author__ = 'kovtash'

class XMPPSessionEventID(object):
    def __init__(self):
        self.__current_id = 0

    def id(self):
        self.__current_id +=1
        return self.__current_id