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
    def __init__(self, *, client, raw=None):
        self.client = client
        self.loop = client.loop
        self.raw_message = raw
        if isinstance(self, DirectMessage): logger.debug('direct message is now an event...') #yes

class Message(Event):
    """Base class for sending text somewhere our client can see it.

    This class will never be fired directly; only a more specific subclass.
    But you can always listen on this class directly to hear all possible
    messages.
    """
    def __init__(self, source, target, message, **kwargs):
        super().__init__(**kwargs)

        self.source = source
        self.target = target
        self.message = message

    @property
    def channel(self):
        """Channel to which the message was sent.  This is populated only for
        public messages.
        """
        # This makes me unhappy, but putting it on PublicMessage means it
        # doesn't work for CommandEvent  :/
        if isinstance(self.target, Channel):
            return self.target
        else:
            return None

class PublicMessage(Message):
    """A public message, i.e. one sent to a channel.

    Any public message addressed directly to the bot will become a
    `CommandMessage` instead, so this event only fires for other forms of
    chatter.  Listen to the `Message` parent class to receive events for all
    messages, whether commands or not.
    """


class PrivateMessage(Message):
    """A private message.  Note that bot plugins will never receive this, as
    all private messages are currently assumed to be commands.
    """


class DirectMessage(Event):
    def __init__(self, client, raw_message):
        logger.debug('making a direct message...') #yes
        super().__init__(client, raw_message)

    @property
    def message(self):
        return self.raw_message

