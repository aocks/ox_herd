"""Module for managing ox_herd plugins.
"""

import os
import logging
import inspect
import importlib
from ox_herd import settings
from ox_herd.core.plugins import base


class PluginManager(object):

    __active_plugins = {}

    @classmethod
    def activate_plugins(cls):
        """Activate plugins.
        """
        active_names = list(settings.OX_PLUGINS)
        active_set = set(active_names)
        env_plugs = os.getenv('OX_PLUGINS', '').split(':')
        for name in env_plugs:
            if name and name not in active_set:
                active_names.append(name)
        for name in active_names:
            if name in cls.__active_plugins:
                logging.warning('Plugin %s already activated; skipping', name)
                continue
            logging.info('Importing %s', name)
            my_mod = importlib.import_module(name)
            plug = cls.make_plugin_from_module(name, my_mod)
            assert isinstance(plug, base.OxPlugin)
            cls.__active_plugins[name] = plug

    @classmethod
    def get_active_plugins(cls):
        return dict(cls.__active_plugins)

    @classmethod
    def make_plugin_from_module(cls, name, my_mod):
        maker = getattr(my_mod, 'get_ox_plugin', None)
        if maker:
            return maker()
        logging.debug('No get_ox_plugin function for plugin %s; %s.',
                      name, 'Using default plugin maker.')
        return cls.default_plugin_maker(name, my_mod)

    @classmethod
    def default_plugin_maker(cls, name, my_mod):
        plugins = []
        klasses = []
        components = []
        for dname in dir(my_mod):
            item = getattr(my_mod, dname)
            if isinstance(item, base.OxPlugin):
                plugins.append((dname, item))
            elif inspect.isclass(item):
                if issubclass(item, base.OxPlugin):
                    klasses.append((dname, item))
                elif issubclass(item, base.OxPluginComponent):
                    components.append((dname, item))
        if plugins:
            if len(plugins) > 1:
                msg = "Can't make default plugin for %s because:\n%s." % (
                    name, ('Found %i plugin candidates: %s' % (
                        len(plugins), [pair[0] for pair in plugins])))
                raise ValueError(msg)
            else:
                return plugins[0][1]
        if klasses:
            if len(klasses) > 1:
                msg = "Can't make default plugin for %s because:\n%s." % (
                    name, ('Found %i plugin candidates classes: %s' % (
                        len(klasses), [pair[0] for pair in klasses])))
                raise ValueError(msg)
            else:
                instances = [c[1](name=c[0]) for c in components]
                return klasses[0][1](components=instances)
        if components:
            instances = [c[1](name=c[0]) for c in components]
            my_plugin = base.TrivialOxPlugin(instances, name, (
                'Automatically created plugin for %s.' % name))
            return my_plugin
            
        msg = 'Could not find any plugins or components in %s' % str(name)
        logging.error('%s\nSearched:\n%s\n', msg, str(list(dir(my_mod))))
        raise ValueError(msg)
            
