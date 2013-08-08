__author__ = 'kovtash'

import asyncore
import logging
from tornado import ioloop
import threading
import xmpp

class XMPPTornadoIOLoopThread(threading.Thread):
    def __init__(self):
        super(XMPPTornadoIOLoopThread, self).__init__()
        self.ioLoop = ioloop.IOLoop()
        self.handlers = self.ioLoop.__dict__['_handlers']

    def run(self):
        self.ioLoop.make_current()
        self.ioLoop.start()

    def stop(self):
        self.ioLoop.stop()

    def add_handler(self, fd, handler, events):
        print(len(self.handlers))
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

    def handle_read(self, fd, events):
        try:
            if self.client.isConnected():
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

        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']._sock
            self.ioLoopThread.add_handler(sock.fileno(), self.handle_read, self.ioLoopThread.ioLoop.READ)

    def stop(self):
        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']._sock
            self.ioLoopThread.remove_handler(sock.fileno())

        self.client.close()

class XMPPTornadoMainIOLoopDispatcher(object):
    def __init__(self, client):
        super(XMPPTornadoMainIOLoopDispatcher, self).__init__()
        self.client = client
        self.ioLoop = ioloop.IOLoop.instance()

    def handle_read(self, fd, events):
        try:
            if self.client.isConnected():
                self.client.Process()
        except xmpp.protocol.StreamError:
            self.client.close()
        except Exception as e:
            logging.exception(e)

    def start(self):
        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']._sock
            self.ioLoop.add_handler(sock.fileno(), self.handle_read, self.ioLoop.READ)

    def stop(self):
        if 'TCPsocket' in self.client.__dict__:
            sock = self.client.__dict__['TCPsocket']._sock
            self.ioLoop.remove_handler(sock.fileno())

        self.client.close()


class XMPPAsyncoreDispatcher(asyncore.dispatcher):
    """Async XMPPClient dispatcher"""

    ioLoopThread = threading.Thread(target=asyncore.loop)

    def __init__(self, client):
        self.client = client
        if 'TCPsocket' in self.client.__dict__:
            asyncore.dispatcher.__init__(self, self.client.__dict__['TCPsocket']._sock)

    def handle_read(self):
        try:
            if self.client.isConnected():
                self.client.Process()
        except xmpp.protocol.StreamError:
            self.close()
        except Exception as e:
            logging.exception(e)

    def handle_close(self):
        self.close()

    def start(self):
        if not XMPPAsyncoreDispatcher.ioLoopThread.isAlive():
            XMPPAsyncoreDispatcher.ioLoopThread = threading.Thread(target=asyncore.loop)
            XMPPAsyncoreDispatcher.ioLoopThread.start()

    def stop(self):
        self.client.close()
        self.close()


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