__author__ = 'kovtash'

import logging
from tornado import ioloop
import threading
import xmpp
from errors import XMPPConnectionError

class XMPPTornadoIOLoopThread(threading.Thread):
    def __init__(self):
        super(XMPPTornadoIOLoopThread, self).__init__()
        self.ioLoop = ioloop.IOLoop()
        self.handlers = self.ioLoop.__dict__['_handlers']
        self.daemon = True

    def run(self):
        self.ioLoop.make_current()
        self.ioLoop.start()

    def stop(self):
        logging.info('DispatcherEvent : stopping ioloop')
        self.ioLoop.stop()

    def add_handler(self, fd, handler, events):
        self.ioLoop.add_handler(fd, handler, events)

    def remove_handler(self, fd):
        self.ioLoop.remove_handler(fd)
        if len(self.handlers) < 2:
            self.stop()


class XMPPTornadoIOLoopDispatcher(object):

    ioLoopThread = XMPPTornadoIOLoopThread()

    def __init__(self, client):
        super(XMPPTornadoIOLoopDispatcher, self).__init__()
        self.client = client
        self.current_sock = None
        client.RegisterConnectHandler(self._connected)
        client.RegisterDisconnectHandler(self._disconnected)

    def _connected(self):
        if self.current_sock is not None:
            self.ioLoopThread.remove_handler(self.current_sock)

        if 'TCPsocket' in self.client.__dict__:
            try:
                self.current_sock = self.client.__dict__['TCPsocket']._sock.fileno()
            except AttributeError:
                self.stop()
                raise XMPPConnectionError

        if  self.current_sock is not None:
            self.ioLoopThread.add_handler(self.current_sock, self.handle_read, self.ioLoopThread.ioLoop.READ)

    def _disconnected(self):
        if self.current_sock is not None:
            try:
                self.ioLoopThread.remove_handler(self.current_sock)
            except KeyError:
                pass
            self.current_sock = None

    def handle_read(self, fd, events):
        try:
            self.client.Process()
        except xmpp.protocol.StreamError:
            self.client.close()
        except Exception as e:
            logging.exception(e)

    def start(self):
        if not XMPPTornadoIOLoopDispatcher.ioLoopThread.isAlive():
            XMPPTornadoIOLoopDispatcher.ioLoopThread = XMPPTornadoIOLoopThread()
            XMPPTornadoIOLoopDispatcher.ioLoopThread.start()
            self.ioLoopThread = XMPPTornadoIOLoopDispatcher.ioLoopThread

        self._connected()

    def stop(self):
        self.client.close()

class XMPPTornadoMainIOLoopDispatcher(object):
    def __init__(self, client):
        super(XMPPTornadoMainIOLoopDispatcher, self).__init__()
        self.client = client
        self.ioLoop = ioloop.IOLoop.instance()
        self.current_sock = None
        client.RegisterConnectHandler(self._connected)
        client.RegisterDisconnectHandler(self._disconnected)

    def _connected(self):
        if self.current_sock is not None:
            self.ioLoop.remove_handler(self.current_sock)

        if 'TCPsocket' in self.client.__dict__:
            try:
                self.current_sock = self.client.__dict__['TCPsocket']._sock.fileno()
            except AttributeError:
                self.stop()
                raise XMPPConnectionError

        if  self.current_sock is not None:
            self.ioLoop.add_handler(self.current_sock, self.handle_read, self.ioLoop.READ)

    def _disconnected(self):
        if self.current_sock is not None:
            self.ioLoop.remove_handler(self.current_sock)
            self.current_sock = None

    def handle_read(self, fd, events):
        try:
            self.client.Process()
        except xmpp.protocol.StreamError:
            self.client.close()
        except Exception as e:
            logging.exception(e)

    def start(self):
        self._connected()

    def stop(self):
        self.client.close()


class XMPPThreadedDispatcher(threading.Thread):
    """Threaded XMPPClient dispatcher"""
    def __init__(self, client):
        super(XMPPThreadedDispatcher, self).__init__()
        self.client = client
        self.keepRunning = True

    def run(self):
        while self.keepRunning:
            try:
                self.client.Process(30)
            except xmpp.protocol.StreamError:
                self.client.close()
                return

        self.client.close()

    def stop(self):
        self.keepRunning = False