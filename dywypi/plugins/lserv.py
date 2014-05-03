from dywypi.plugin import Plugin, PublicMessage

from pathlib import Path
import re
import logging

plugin = Plugin('lserv', '@')

logger = logging.getLogger(__name__)

PATH = u"INSERT_TEST_PATH_HERE" #make sure this takes unicode
TYPES = ["cbr", "cbz", "chm", "djvu", "docx?", "epub",
    "fb2", "html?", "lit", "lrf", "mobi", "odt",
    "pdb", "pdf", "prc", "rar", "rtf", "txt", "zip"]

ts = '^[^\.].*('
for t in TYPES:
    ts = ts + t + '|'
tf = re.compile(ts[:-1] + ')$')

def safe_add(d, k, v, msg):
    if k not in d:
        d[k] = v
    else:
        logger.warning(msg.format(v, d[k]))

fs = {}
lp = Path(PATH)
if lp.is_dir():
    for p in lp.glob('**/*'):
        if tf.match(p.name):
            safe_add(fs, p.name, p, '"{0}" collides with file "{1}" and will not be served.')
        #progress indicator?
        #TODO write to file--better caching, allows download of list (required). reserve filename?
        #can i load from dir, then start serving while writing? should be able to, duh async
        #TODO one bot serving multiple lists
elif lp.is_file():
    l = lp.open()
    for line in l:
        p = Path(line)
        if p.is_file() and tf.match(p.name):
            safe_add(fs, p.name, p, '"{0}" collides with file "{1}" and will not be served.')
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
        yield from event.reply("{0} ({1})".format(r, prettysize(results[r].stat().st_size)), private=True)

@plugin.on(PublicMessage)
def send(event):
    if event.message == '@'+event.client.nick: #can't implement as command; no access to nick w/o event :\
        pass #send list
    elif event.message.startswith('!'+event.client.nick):
        request = fs[event.message[len(event.client.nick)+2:]]
        logger.debug('Ready to serve file at '+str(request))
        #send file. require ctcp/dcc plugin; that works, right?

