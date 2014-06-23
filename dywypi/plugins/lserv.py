from dywypi.plugin import Plugin, PublicMessage

import re
from pathlib import Path
from unidecode import unidecode
import random
import logging

import dywypi.plugins.ctcp

plugin = Plugin('lserv', '@')

logger = logging.getLogger(__name__)

#TODO all this stuff needs to go in config.
LISTS = {"": u"PATH", "-1": u"PATH-1"}
TYPES = ["cbr", "cbz", "chm", "djvu", "docx?",
    "epub", "fb2", "html?", "lit", "lrf",
    "mht", "mobi", "odt", "pdb", "pdf",
    "prc", "rar", "rtf", "txt", "zip"]
PORT_RANGE = (0, 0)
BARK = ""

tf = re.compile('^[^\.].*\.(' + '|'.join(TYPES) + ')$')

def safe_add(d, k, v, msg):
    if k not in d:
        d[k] = v
    else:
        logger.warning(msg.format(v, d[k]))

def add_file_from_path(d, p):
    if tf.match(p.name):
        safe_add(d, p.name, p, '"{0}" collides with file "{1}" and will not be served.')

def add_from_path(d, p):
    if p.is_dir():
        for path in lp.glob('**/*'):
            add_file_from_path(d, path)
    elif p.is_file():
        add_file_from_path(d, p)
    else:
        logger.warning('"{0}" is not a valid file or directory and will not be served.'.format(p))

ls = {}
for l in LISTS:
    fs = {}
    lp = Path(LISTS[l])
    if lp.is_dir():
        add_from_path(fs, p)
        #progress indicator?
    elif lp.is_file():
        lf = lp.open()
        for line in lf:
            p = Path(line)
            add_from_path(fs, p)
            #TODO smarter error checking (don't log a million warnings if one external drive is missing)
    else:
        logger.error('Path for list "{0}" not found; nothing will be served!'.format(l))
    ls[l] = fs

def and_search(terms, string):
    for term in terms:
        if not re.search(term, string, re.I):
            return False
    return True

@plugin.command('write') #this should be a protected command
def write_listfiles(event):
    for l in LISTS:
        if Path(LISTS[l]).is_dir():
            f = open(str(Path(LISTS[l]) / (event.client.nick + l + '.txt')), 'w')
            for k in sorted(ls[l]):
                f.write('!' + event.client.nick + ' ' + k + ' (' + prettysize(ls[l][k].stat().st_size) + ')\n')
        #TODO find a place to write lists from flat files

@plugin.command('bark') #this too (not to mention properly scheduled)
def start_barking(event):
    c = None
    if event.args:
        c = event.args[0]
        if c not in event.client.joined_channels:
            yield from event.reply("Not in channel {0}".format(c))
            return
    import asyncio
    while True:
        if c:
            yield from event.client.say(BARK, c)
        else:
            for channel in event.client.joined_channels:
                yield from event.client.say(BARK, channel)
        yield from asyncio.sleep(60)

def prettysize(b):
    if b < 1024.0:
        return '{0} bytes'.format(b)
    for u in ['KB', 'MB', 'GB']:
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
    nick = event.client.nick
    for l in ls:
        results = {f: ls[l][f] for f in ls[l] if and_search(map(unidecode, event.args), unidecode(f))}
        if len(results) > 0:
            yield from event.reply("From list {0}{1}:".format(nick, l), private=True)
            for r in sorted(results):
                yield from event.reply("!{0}{1} {2} ({3})".format(nick, l, r,
                    prettysize(results[r].stat().st_size)), private=True)
            found = True
    if not found and not event.channel:
        yield from event.reply("Sorry, nothing found for '{0}'.".format(' '.join(event.args)))

def get_port():
    return random.randint(*PORT_RANGE)

@plugin.on(PublicMessage)
def send(event):
    nick = event.client.nick

    if event.message.startswith('!'+nick):
        try:
            l, r = event.message.split(' ', 1)
            list_name = l[len(nick)+1:]
            if list_name not in ls:
                yield from event.reply("Sorry, list '{0}{1}' not found.".format(nick, list_name), private=True)
            request = ls[list_name][r]
            logger.debug('Ready to serve file at '+str(request))
            yield from dywypi.plugins.ctcp.transfer(event, request, get_port())
        except ValueError:
           yield from event.reply("Please make sure there is a space between "+
               "the list name and file name of your request.", private=True)
        except KeyError:
           yield from event.reply("Sorry, file '{0}' not found in list '{1}{2}'."
               .format(r, nick, list_name), private=True)
           results = ["'{0}{1}'".format(nick, l) for l in ls if r in ls[l]]
           if len(results) > 0:
               yield from event.reply("File '{0}' *is* listed in {1}.".format(r, prettylist(results)), private=True)

    elif event.message.startswith('@'+nick):
        list_name = event.message.split(nick)[1]
        try:
            list_path = Path(LISTS[list_name])
            if list_path.is_dir(): #um. try to keep track of these better.
                yield from dywypi.plugins.ctcp.transfer(event, list_path / (nick + list_name + '.txt'), get_port())
            else:
                pass #yeah i have no idea where you would put these. these both should go in config
        except KeyError:
            yield from event.reply("Sorry, list '{0}' not found.".format(event.message.lstrip('@')), private=True)
