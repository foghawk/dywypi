from dywypi.plugin import Plugin

from dywypi.dialect.dcc import DCCClient
from dywypi.state import Network, Server
from dywypi.event import DirectMessage

import pkg_resources
import datetime
import ipaddress
import logging

plugin = Plugin('ctcp')

logger = logging.getLogger(__name__)

@plugin.command('ctcp-VERSION')
def version(event):
	yield from event.reply("\x01VERSION dywypi {0}\x01".format(pkg_resources.get_distribution("dywypi").version), no_respond=True)

@plugin.command('ctcp-PING')
def ping(event):
	yield from event.reply("\x01PING {0}\x01".format(event.message[10:]), no_respond=True)

@plugin.command('ctcp-TIME')
def time(event):
	yield from event.reply("\x01TIME {0}\x01".format(datetime.datetime.now().isoformat()), no_respond=True)

@plugin.command('ctcp-DCC')
def dcc(event):
	if event.args[0] == 'CHAT':
		std_ip = str(ipaddress.ip_address(int(event.args[2])))
		net = Network(std_ip)
		net.add_server(std_ip, int(event.args[3]))
		dcc_client = DCCClient(event.loop, net)
		try:
			yield from dcc_client.connect()
			yield from dcc_client.send_message("hello!")
		except TimeoutError:
			yield from event.reply("Sorry, it looks like I can't open a direct chat connection. This could be because of settings on your IRC client, firewall, router, and/or proxy.")

@plugin.on(DirectMessage)
def dcc_echo(event):
	logger.debug("got a direct message!") #no
	logger.debug("it's '" +event.message+ "'")
	yield from event.client.say(event.message)
