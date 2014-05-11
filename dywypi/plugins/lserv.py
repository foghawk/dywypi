from dywypi.plugin import Plugin, PublicMessage

from pathlib import Path
import re
from unidecode import unidecode
import logging

plugin = Plugin('lserv', '@')

logger = logging.getLogger(__name__)

#TODO all this stuff needs to go in config.
LISTS = {"": u"PATH", "-1": u"PATH-1"}
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

ls = {}
for l in LISTS:
    fs = {}
    lp = Path(LISTS[l])
    if lp.is_dir():
        for p in lp.glob('**/*'):
            if tf.match(p.name):
                safe_add(fs, p.name, p, '"{0}" collides with file "{1}" and will not be served.')
            #progress indicator?
            #TODO write to file--better caching, allows download of list (required). reserve filename?
            #can i load from dir, then start serving while writing? should be able to, duh async
    elif lp.is_file():
        lf = lp.open()
        for line in lf:
            p = Path(line)
            if p.is_file() and tf.match(p.name):
                safe_add(fs, p.name, p, '"{0}" collides with file "{1}" and will not be served.')
            else:
                logger.warning('"{0}" is not a valid file and will not be served.'.format(line))
                #TODO smarter error checking (don't log a million warnings if one external drive is missing)
    else:
        logger.error('Path for list "{0}" not found; nothing will be served!'.format(l))
    ls[l] = fs

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

def prettylist(l):
    n = len(l)
    if n == 0: return ''
    if n == 1: return '{0}'.format(l[0])
    if n == 2: return '{0} and {1}'.format(l[0], l[1])
    return '{0}, and {1}'.format(', '.join(l[:-1]), l[-1])

@plugin.command('find')
def find(event):
    found = False
    for l in ls:
        results = {f: ls[l][f] for f in ls[l] if and_search(event.args, unidecode(f))}
        if len(results) > 0:
            yield from event.reply("From list {0}{1}:".format(event.client.nick, l), private=True)
            for r in results:
                yield from event.reply("{0} ({1})".format(r, prettysize(results[r].stat().st_size)), private=True)
            found = True
    if not found and not event.channel:
        yield from event.reply("Sorry, nothing found for '{0}'.".format(' '.join(event.args)))

@plugin.on(PublicMessage)
def send(event):
    nick = event.client.nick
    if event.message.startswith('@'+nick): #can't implement as command; no access to nick w/o event :\
        pass #send list
    elif event.message.startswith('!'+nick):
        try:
            l, r = event.message.split(' ', 1)
            list_name = l[len(nick)+1:]
            if list_name not in ls:
                yield from event.reply("Sorry, list '{0}{1}' not found.".format(nick, list_name), private=True)
            request = ls[list_name][r]
            logger.debug('Ready to serve file at '+str(request))
            #send file. require ctcp/dcc plugin; that works, right?
        except ValueError:
           yield from event.reply("Please make sure there is a space between "+
               "the list name and file name of your request.", private=True)
        except KeyError:
           yield from event.reply("Sorry, file '{0}' not found in list '{1}{2}'."
               .format(r, nick, list_name), private=True)
           results = ["'{0}{1}'".format(nick, l) for l in ls if r in ls[l]]
           if len(results) > 0:
               yield from event.reply("File '{0}' *is* listed in {1}.".format(r, prettylist(results)), private=True)

