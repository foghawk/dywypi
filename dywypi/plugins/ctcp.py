from dywypi.plugin import Plugin

from dywypi.dialect.dcc import DCCClient
from dywypi.state import Network, Server
from dywypi.event import DirectMessage

import dywypi.__about__

import datetime
import ipaddress
import logging

plugin = Plugin('ctcp')

logger = logging.getLogger(__name__)

@plugin.command('ctcp-CLIENTINFO')
def clientinfo(event):
    """Lists CTCP commands I support."""
    command_list = sorted([c[5:] for c in plugin.commands if c.startswith('ctcp-')])
    if not event.args:
        yield from event.reply("\x01CLIENTINFO I support the CTCP commands {0}, and {1}. Use CLIENTINFO <COMMAND> for help.\x01"
            .format(", ".join(str(c) for c in command_list[:-1]), command_list[-1]), no_respond=True)
    else:
        for arg in event.args:
            arg = arg.upper()
            if arg in command_list:
                yield from event.reply("\x01CLIENTINFO {0}: {1}\x01"
                    .format(arg, ' '.join(plugin.commands['ctcp-'+arg].coro.__doc__.split())), no_respond=True)
            else:
                yield from event.reply("\x01CLIENTINFO {0}: Not a supported command.\x01".format(arg), no_respond=True)

@plugin.command('ctcp-VERSION')
def version(event):
    """Returns the version of the client I am running."""
    yield from event.reply("\x01VERSION dywypi {0}\x01".format(dywypi.__about__.__version__), no_respond=True)

@plugin.command('ctcp-SOURCE')
def source(event):
    """Returns a URL where you can get the source of the client I am running."""
    yield from event.reply("\x01SOURCE {0}\x01".format(dywypi.__about__.__uri__), no_respond=True)

@plugin.command('ctcp-PING')
def ping(event):
    """Echoes whatever data (usually a timestamp) I receive, allowing your client to calculate the round-trip time.
    This can be used to test connection speeds. Most clients use "/ping <nick>"."""
    yield from event.reply("\x01PING {0}\x01".format(event.message[10:]), no_respond=True)

@plugin.command('ctcp-TIME')
def time(event):
    """Returns my local time."""
    yield from event.reply("\x01TIME {0}\x01".format(datetime.datetime.now().isoformat()), no_respond=True)

@plugin.command('ctcp-DCC')
def dcc(event):
    """Used to initiate a server-independent Direct Client Connection, either for chat or for file transfers.
    Most clients use "/dcc chat <nick>" or "/dcc send <nick> <file>". (I do not respond to commands over DCC or auto-accept files.)"""
    if event.args[0] == 'CHAT':
        std_ip = str(ipaddress.ip_address(int(event.args[2])))
        net = Network(std_ip) #event loop DOES NOT WORK because Brain does not have a reference to this network. how to give it one?
        net.add_server(std_ip, int(event.args[3]))
        dcc_client = DCCClient(event.loop, net)
        try:
            yield from dcc_client.connect()
            yield from dcc_client.send_message("hello!")
        except TimeoutError:
            yield from event.reply("Sorry, it looks like I can't open a direct chat connection. "+
                "This could be because of settings on your IRC client, firewall, router, and/or proxy.")

@plugin.on(DirectMessage)
def dcc_echo(event):
    logger.debug("got a direct message!") #no
    logger.debug("it's '" +event.message+ "'")
    yield from event.client.say(event.message)
