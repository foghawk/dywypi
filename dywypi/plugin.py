import asyncio
from collections import defaultdict
import importlib
import logging
import pkgutil

from dywypi.event import Event, Message, _MessageMixin, DirectMessage

log = logging.getLogger(__name__)


class EventWrapper:
    """Little wrapper around an event object that provides convenient plugin
    methods like `reply`.  All other attributes are delegated to the real
    event.
    """
    def __init__(self, event, plugin_data, plugin_manager):
        self.event = event
        self.type = type(event)
        self.plugin_data = plugin_data
        self._plugin_manager = plugin_manager

    @property
    def data(self):
        return self.plugin_data

    # TODO should this just be on Event?
    @asyncio.coroutine
    def reply(self, message, private=False, no_respond=False):
        if self.event.channel and not private:
            reply_to = self.event.channel.name
        else:
            reply_to = self.event.source.name

        # TODO uhoh, where does this guy belong...
        # TODO and where does the formatting belong...  on a Dialect?  which is
        # not yet a thing?
        from dywypi.formatting import FormattedString
        if isinstance(message, FormattedString):
            # TODO this should probably be a method on the dialect actually...?
            message = message.render(self.event.client.format_transition)
        yield from self.event.client.say(message, reply_to, no_respond)

    def __getattr__(self, attr):
        return getattr(self.event, attr)


class PluginEvent(Event):
    """Base class for special plugin-only events that don't make sense for
    generic clients.  Usually more specific versions of main dywypi events, to
    allow for finer-grained listening in plugins.
    """


class PublicMessage(PluginEvent, _MessageMixin):
    pass


class Command(PluginEvent, _MessageMixin):
    def __init__(self, client, raw_message, command_name, argstr):
        super().__init__(client, raw_message)
        self.command_name = command_name
        self.argstr = argstr
        self.args = argstr.strip().split()

    def __repr__(self):
        return "<{}: {} {!r}>".format(
            type(self).__qualname__, self.command_name, self.args)


class PluginManager:
    def __init__(self):
        self.loaded_plugins = {}
        self.loaded_prefixes = {}
        self.plugin_data = defaultdict(dict)

    @property
    def known_plugins(self):
        """Returns a dict mapping names to all known `Plugin` instances."""
        return BasePlugin._known_plugins

    @property
    def known_prefixes(self):
        return {p.prefix: p.name for p in self.known_plugins.values() if p.prefix}

    def scan_package(self, package='dywypi.plugins'):
        """Scans a Python package for in-process Python plugins."""
        pkg = importlib.import_module(package)
        # TODO pkg.__path__ doesn't exist if pkg is /actually/ a module
        for finder, name, is_pkg in pkgutil.iter_modules(pkg.__path__, prefix=package + '.'):
            try:
                importlib.import_module(name)
            except ImportError as exc:
                log.error(
                    "Couldn't import plugin module {}: {}"
                    .format(name, exc))

    def loadall(self):
        for name, plugin in self.known_plugins.items():
            self.load(name)

    def load(self, plugin_name):
        if plugin_name in self.loaded_plugins:
            return
        # TODO keyerror
        plugin = self.known_plugins[plugin_name]
        #plugin.start()
        log.info("Loaded plugin {}".format(plugin.name))
        self.loaded_plugins[plugin.name] = plugin
        if (plugin.prefix): self.loaded_prefixes[plugin.prefix] = plugin.name

    def loadmodule(self, modname):
        # This is a little chumptastic, but: figure out which plugins a module
        # adds by comparing the list of known plugins before and after.
        # TODO lol this doesn't necessarily work if the module was already
        # loaded.  this is dumb just allow scanning particular packages
        before_plugins = set(self.known_plugins)
        importlib.import_module(modname)
        after_plugins = set(self.known_plugins)

        for plugin_name in after_plugins - before_plugins:
            self.load(plugin_name)

    def _wrap_event(self, event, plugin):
        return EventWrapper(event, self.plugin_data[plugin], self)

    def _fire(self, event):
        futures = []
        for plugin in self.loaded_plugins.values():
            futures.extend(self._fire_on(event, plugin))
        return futures

    def _fire_on(self, event, plugin):
        wrapped = self._wrap_event(event, plugin)
        return plugin.fire(wrapped)

    def _fire_global_command(self, command_event):
        # TODO well this could be slightly more efficient
        # TODO should also mention when no command exists
        futures = []
        for plugin in self.loaded_plugins.values():
            if not plugin.prefix:
                wrapped = self._wrap_event(command_event, plugin)
                plugin.fire_command(wrapped, is_global=True)
            wrapped = self._wrap_event(command_event, plugin)
            futures.extend(plugin.fire_command(wrapped, is_global=True))
        return futures

    def _fire_plugin_command(self, plugin_name, command_event):
        # TODO should DEFINITELY complain when plugin OR command doesn't exist
        try:
            plugin = self.loaded_plugins[plugin_name]
        except KeyError:
            raise
            # TODO
            #raise SomeExceptionThatGetsSentAsAReply(...)

        wrapped = self._wrap_event(command_event, plugin)
        return plugin.fire_command(wrapped, is_global=False)

    def fire(self, event):
        if isinstance(event, DirectMessage):
            log.debug("firing a direct message...")

        self._fire(event)
        futures = self._fire(event)

        # Possibly also fire plugin-specific events.
        if isinstance(event, Message):
            # Messages get broken down a little further.
            is_public = (event.channel)
            is_command = (event.message.startswith(event.client.nick) and
                (event.message != event.client.nick and
                event.message[len(event.client.nick)] in ':, '))

            if is_command or not is_public or event.message.startswith(tuple(self.loaded_prefixes)):
                # Something addressed directly to us; this is a command and
                # needs special handling!
                if is_command:
                    message = event.message[len(event.client.nick) + 1:].strip()
                else:
                    message = event.message
                plugin_name = None
                for prefix in self.loaded_prefixes: #ugh
                    if message.startswith(prefix):
                        plugin_name = self.loaded_prefixes[prefix]
                        message = message[len(prefix):]
                        break #ew 
                try:
                    command_name, argstr = message.split(None, 1)
                except ValueError:
                    command_name, argstr = message.strip(), ''

                command_event = Command.from_event(
                    event,
                    command_name=command_name,
                    argstr=argstr,
                )
                log.debug('Firing command %r', command_event)
                if plugin_name:
                    futures.extend(
                        self._fire_plugin_command(plugin_name, command_event))
                else:
                    futures.extend(
                        self._fire_global_command(command_event))
            else:
                # Regular public message.
                futures.extend(
                    self._fire(PublicMessage.from_event(event)))

            # TODO: what about private messages that don't "look like"
            # commands?  what about "all" public messages?  etc?

        return futures


class PluginCommand:
    def __init__(self, coro, *, is_global):
        self.coro = coro
        self.is_global = is_global


class BasePlugin:
    _known_plugins = {}

    def __init__(self, name):
        if name in self._known_plugins: # TODO check for prefix collision too
            raise NameError(
                "Can't have two plugins named {}: {} versus {}"
                .format(
                    name,
                    self.__module__,
                    self._known_plugins[name].__module__))

        self.name = name
        self._known_plugins[name] = self


class Plugin(BasePlugin):
    def __init__(self, name, prefix=None):
        self.listeners = defaultdict(list)
        self.commands = {}
        self.prefix = prefix

        super().__init__(name)

    def on(self, event_cls):
        if not issubclass(event_cls, Event):
            raise TypeError("Can only listen on an Event subclass, not {}".format(event_cls))

        def decorator(f):
            coro = asyncio.coroutine(f)
            for cls in event_cls.__mro__:
                if cls is Event:
                    # Ignore Event and its superclasses (presumably object)
                    break
                self.listeners[cls].append(coro)
            return coro

        return decorator

    def command(self, command_name, *, is_global=True):
        def decorator(f):
            coro = asyncio.coroutine(f)
            # TODO collisions etc
            self.commands[command_name] = PluginCommand(
                coro, is_global=is_global)
            return coro
        return decorator

    ### "Real" methods

    def fire(self, event):
        """Fire the given event, by dumping all the associated listeners on
        this plugin into the event loop.

        Returns a sequence of Futures, one for each listener (and possibly
        zero).  Event handlers aren't expected to have any particular result,
        but the caller might be interested in one for particular event types,
        or may wish to handle exceptions.
        """
        futures = []
        for listener in self.listeners[event.type]:
            # Fire them all off in parallel via async(); `yield from` would run
            # them all in serial and nonblock until they're all done!
            # TODO if there are exceptions here they're basically lost; whoever
            # asked for the event will never get an error message, and e.g.
            # py.test will never get a traceback
            futures.append(asyncio.async(listener(event), loop=event.loop))
        return futures

    def fire_command(self, event, *, is_global):
        """Fire a command event.  Return a sequence of Futures.  See `fire`.
        """
        futures = []
        if event.command_name in self.commands:
            command = self.commands[event.command_name]
            # # Don't execute if the command is local-only and this wasn't
            # # invoked with a prefix
            # lol nope this happens in the parser now
            #if command.is_global or not is_global:
            asyncio.async(command.coro(event), loop=event.loop)

            # Don't execute if the command is local-only and this wasn't
            # invoked with a prefix
            if command.is_global or not is_global:
                futures.append(
                    asyncio.async(command.coro(event), loop=event.loop))

        return futures


class PluginError(Exception): pass
