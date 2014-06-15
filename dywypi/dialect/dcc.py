import asyncio
from asyncio.queues import Queue
from concurrent.futures import CancelledError
from dywypi.event import DirectMessage

import socket
import re
import logging

logger = logging.getLogger(__name__)

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
    def __init__(self, loop, network, send=False):
        self.loop = loop
        self.network = network
        self.read_queue = Queue(loop=loop)
        self.send = send #ugh what if i want to RECEIVE though.
        #not sure what the use case would be but...?

    @asyncio.coroutine
    def connect(self, port=None):
        if not self.send:
            server = self.current_server = self.network.servers[0]
            self._reader, self._writer = yield from server.connect(self.loop)
            self._read_loop_task = asyncio.Task(self._start_read_loop())
            asyncio.async(self._read_loop_task, loop=self.loop)
        else:
            self._waiting = asyncio.Lock()
            yield from self._waiting.acquire()
            if port:
                self.network = yield from asyncio.start_server(self._handle_client,
                    host=socket.gethostbyname(socket.gethostname()), port=port, loop=self.loop)
            else:
                logger.error("No port provided for send")

    @asyncio.coroutine
    def _handle_client(self, client_reader, client_writer):
        self._reader = client_reader
        self._writer = client_writer
        self._waiting.release()
        self._read_loop_task = asyncio.Task(self._start_read_loop())
        asyncio.async(self._read_loop_task, loop=self.loop)

    @asyncio.coroutine
    def disconnect(self):
        yield from self._writer.drain()
        self._writer.write_eof()

        self._read_loop_task.cancel()
        yield from self._read_loop_task

        while not self._reader.at_eof():
            yield from self._reader.readline()

        if self.send:
            self.network.close()

    @asyncio.coroutine
    def _start_read_loop(self):
        if not self.send: #acks don't really do anything so don't listen for them
            while not self._reader.at_eof():
                try:
                    yield from self._read_message()
                except CancelledError:
                    return
                except Exception:
                    logger.exception("Smothering exception in DCC read loop")

    @asyncio.coroutine
    def _read_message(self):
         line = yield from self._reader.readline()
         m = re.match(b'(.*)(\r|\n|\r\n)$', line)
         assert m
         line = m.group(1)
         message = DCCMessage.parse(line)
         logger.debug("recv: %r", message)
         event = DirectMessage(self, message)
         self.read_queue.put_nowait((message, event))

    @asyncio.coroutine
    def read_event(self):
        message, event = yield from self.read_queue.get()
        return event

    @asyncio.coroutine
    def say(self, message, target=None, no_respond=None):
        self.send_message(message)

    @asyncio.coroutine
    def send_message(self, message):
        message = DCCMessage(message)
        logger.debug("sent: %r", message)
        self._writer.write(message.render().encode('utf8') + b'\r\n')

    @asyncio.coroutine
    def transfer(self, path):
        yield from self._waiting.acquire()
        f = open(str(path), 'rb')
        block = b'\x01'
        while block != b'':
            block = f.read(1024)
            self._writer.write(block)
        f.close()
        self._waiting.release()
        return True
