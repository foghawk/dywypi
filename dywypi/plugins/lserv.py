from dywypi.plugin import Plugin, PublicMessage
from dywypi.state import Peer

import os
import re
import logging

plugin = Plugin('lserv')

logger = logging.getLogger(__name__)

PATH = u"INSERT_TEST_PATH_HERE" #make sure this takes unicode

fs = []
if os.path.isdir(PATH):
	for rootpath, dirs, files in os.walk(PATH):
		for name in files:
			fs.append((rootpath, name))
			#progress indicator? filetype filter?
			#TODO write to file--better caching, allows download of list (required). reserve filename?
			#can i load from dir, then start serving while writing? should be able to, duh async
			#TODO one bot serving multiple lists
elif os.path.isfile(PATH):
	l = open(PATH)
	for line in l:
		if os.path.isfile(line):
			fs.append(os.path.split(line))
		else:
			logger.warning('"{0}" is not a valid file and will not be served.'.format(line))
			#TODO smarter error checking (don't log a million warnings if one external drive is missing)
else:
	logger.error('List path not found')



def and_search(terms, string):
	for term in terms:
		if not re.search(term, string, re.I):
			return False
	return True

def prettysize(b):
	for u in ['bytes', 'KB', 'MB', 'GB', 'TB']:
		if b < 1024.0:
			return '{0:.2f} {1}'.format(b, u)
		b /= 1024.0
	return '{0:.2f} TB'.format(b)

@plugin.on(PublicMessage) #boo this is hacky
def public_find(event):
	if event.message[0:5] == '@find':
		logger.debug('Ready to fire @find command...')
		event.client.say(Peer(event.client.nick, None, None), event.message) #this doesn't work idkoc why rn

@plugin.command('@find')
def find(event):
	results = [f for f in fs if and_search(event.args, f[1])]
	if len(results) == 0 and not event.channel:
		yield from event.reply("Sorry, nothing found for '{0}'.".format(event.message[6:]))
	for r in results:
		yield from event.reply("{0} ({1})".format(r[1], prettysize(os.path.getsize(os.path.join(r[0], r[1])))), private=True)

#@plugin.command('!'+event.client.nick) #download list (no args) or file (args)


