"""Event classes.

As dywypi makes a vain attempt to be protocol-agnostic, these should strive to
be so as well, and anything specific to a particular protocol should indicate
as such in its name.
"""
from dywypi.state import Channel, Peer

import logging
logger = logging.getLogger(__name__)

class Event:
    """Something happened."""
    # TODO starting to think the raw message should get far far less focus
    # here, and instead the constructors should pull this stuff out
    def __init__(self, client, raw_message):
        self.client = client
        self.loop = client.loop
        self.raw_message = raw_message
        if isinstance(self, DirectMessage): logger.debug('direct message is now an event...') #yes

    @classmethod
    def from_event(cls, event, *args, **kwargs):
        return cls(event.client, event.raw_message, *args, **kwargs)

    @property
    def source(self):
        return self.client.source_from_message(self.raw_message)


class _MessageMixin:
    """Provides some common accesors used by both the regular `Message` event
    and some special specific plugin events.
    """
    @property
    def target(self):
        """Where the message was directed; either a `Channel` (for a public
        message) or a `Peer` (for a private one).
        """
        # TODO this should absolutely be on the client wow
        target_name = self.raw_message.args[0]
        if target_name[0] in '#&!':
            return self.client.get_channel(target_name)
        else:
            # TODO this too but less urgent
            # TODO this is actually /us/, so.
            return Peer(target_name, None, None)

    @property
    def channel(self):
        """Channel where the message occurred, or None if this was a private
        message.
        """
        target = self.target
        # TODO lol this is so hacky; give them is_* accessors plz
        if isinstance(target, Peer):
            return None
        else:
            return target

    @property
    def message(self):
        return self.raw_message.args[1]

class Message(Event, _MessageMixin):
    pass


class DirectMessage(Event):
    def __init__(self, client, raw_message):
        logger.debug('making a direct message...') #yes
        super().__init__(client, raw_message)

    @property
    def message(self):
        return self.raw_message
