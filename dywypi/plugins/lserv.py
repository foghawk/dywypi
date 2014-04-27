from dywypi.plugin import Plugin, PublicMessage

import os
import re
import logging

plugin = Plugin('lserv', '@')

logger = logging.getLogger(__name__)

PATH = u"INSERT_TEST_PATH_HERE" #make sure this takes unicode

def safe_add(d, k, v, msg):
	if k not in d:
		d[k] = v
	else:
		logger.warning(msg.format(v, d[k]))

fs = {}
if os.path.isdir(PATH):
	for rootpath, dirs, files in os.walk(os.path.abspath(PATH)):
		for name in files:
			filename = os.path.basename(name)
			if filename[0] != '.': #fold this into filetype filter later
				file_path = os.path.join(rootpath, name)
				safe_add(fs, filename, file_path,
					'"{0}" collides with file "{1}" and will not be served.')
			#progress indicator? filetype filter?
			#TODO write to file--better caching, allows download of list (required). reserve filename?
			#can i load from dir, then start serving while writing? should be able to, duh async
			#TODO one bot serving multiple lists
elif os.path.isfile(PATH):
	l = open(PATH)
	for line in l:
		if os.path.isfile(line):
			safe_add(fs, os.path.basename(line), line,
				'"{0}" collides with file "{1}" and will not be served.')
		else:
			logger.warning('"{0}" is not a valid file and will not be served.'.format(line))
			#TODO smarter error checking (don't log a million warnings if one external drive is missing)
else:
	logger.error('List path not found; nothing will be served!')

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

@plugin.command('find')
def find(event):
	results = {f: fs[f] for f in fs if and_search(event.args, f)}
	if len(results) == 0 and not event.channel:
		yield from event.reply("Sorry, nothing found for '{0}'.".format(event.message[6:]))
	for r in results:
		yield from event.reply("{0} ({1})".format(r, prettysize(os.path.getsize(os.path.join(r, results[r])))), private=True)

@plugin.on(PublicMessage)
def send(event):
	if event.message == '@'+event.client.nick: #can't implement as command; no access to nick w/o event :\
		pass #send list
	elif event.message.startswith('!'+event.client.nick):
		request = fs[event.message[len(event.client.nick)+2:]]
		logger.debug('Ready to serve file at '+request)
		#send file. require ctcp/dcc plugin; that works, right?

