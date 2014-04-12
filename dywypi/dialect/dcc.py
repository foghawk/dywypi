import asyncio
from asyncio.queues import Queue
from dywypi.event import DirectMessage
import logging
import re

logger = logging.getLogger(__name__)

class DCCClientProtocol(asyncio.Protocol):
    def __init__(self, loop, charset='utf8'):
        self.charset = charset

        self.buf = b''
        self.message_queue = Queue(loop=loop)
        self.registered = False

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        data = self.buf + data
        while True:
            split = re.split(b'\r?\n?', data, maxsplit=1)
            raw_message = split[0]
            data = b''
            if len(split) == 1:
                # Incomplete message; stop here and wait for more
                self.buf = raw_message
                return
            data = split[1]

            # TODO valerr
            message = DCCMessage.parse(raw_message.decode(self.charset))
            logger.debug("recv: %r", message)
            self.handle_message(message)

    def handle_message(self, message):
        self.message_queue.put_nowait(message)

    def send_message(self, message):
        message = DCCMessage(message)
        logger.debug("sent: %r", message)
        self.transport.write(message.render().encode(self.charset) + b'\r\n')

    @asyncio.coroutine
    def read_message(self):
        return (yield from self.message_queue.get())


class DCCMessage:
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return "<{name}: '{message}'>".format(
            name=type(self).__name__,
            message=self.message,
        )

    def render(self):
        """String representation of a DCC message.  DOES NOT include the
        trailing newlines.
        """
        return self.message

    @classmethod
    def parse(cls, string):
        #parsing what parsing
        return cls(string)


class DCCClient:
    def __init__(self, loop, network):
        self.loop = loop
        self.network = network
        self.event_queue = Queue(loop=loop)

    @asyncio.coroutine
    def connect(self):
        server = self.current_server = self.network.servers[0]
        _, self.proto = yield from self.loop.create_connection(
            lambda: DCCClientProtocol(self.loop), server.host, server.port)

        #check for connection? how tho

        asyncio.async(self._advance(), loop = self.loop)

    def disconnect(self):
        self.proto.transport.close()

    @asyncio.coroutine
    def _advance(self):
        yield from self._read_message()
        asyncio.async(self._advance(), loop=self.loop)

    @asyncio.coroutine
    def _read_message(self):
         message = yield from self.proto.read_message()
         event = DirectMessage(self, message)
         self.event_queue.put_nowait(event)

    @asyncio.coroutine
    def read_event(self):
        return(yield from self.event_queue.get())

    @asyncio.coroutine
    def say(self, message):
        yield from self.send_message(message)

    @asyncio.coroutine
    def send_message(self, message):
        self.proto.send_message(message)
