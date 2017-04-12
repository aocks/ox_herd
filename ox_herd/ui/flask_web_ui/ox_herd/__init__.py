"""Flask Blueprnit for ox_herd.

This module provides the OX_HERD_BP variable representing the main
ox_herd blueprint. If you are incorporating ox_herd into your own
flask application, you should call register_blueprint(OX_HERD_BP)
appropriately.
"""

import logging
from flask import Blueprint
from ox_herd.core.plugins import manager as plugin_manager

class OxHerdBlueprint(Blueprint):
    """Subclass flask Blueprint to provide custom blueprint for ox_herd.

    Mainly this blueprint overrides register to make sure to start plugins.
    """
    
    def register(self, app, *args, **kwargs):
        """Override default register method to also activate plugins.
        
        :arg app, *args, **kwargs:  As for usual Blueprint.register method.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:  As usual for Blueprint.register.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:   Override registration so we can start plugins.
        
        """
        result = Blueprint.register(self, app, *args, **kwargs)
        self.start_oh_plugins(app)
        return result
        
    def start_oh_plugins(self, app):
        """Start ox_herd plugins. Meant to be called by register method.
        
        :arg app:    Flask app we are using to regsiter blueprints.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:   This method finds active plugins, registers any blueprints
                   those plugins provide, and generally gets the plugin
                   manager setup.
        """
        manager = plugin_manager.PluginManager()
        manager.activate_plugins()
        actives = manager.get_active_plugins()
        logging.warning('Activating plugins: %s', str(actives))
        for pname, plug in actives.items():
            bprint = plug.get_flask_blueprint()
            if bprint and not isinstance(bprint, Blueprint):
                raise TypeError(
                    'Plugin %s.get_flask_blueprint gave %s not Blueprint' % (
                        pname, str(bprint)))
            if bprint:
                app.register_blueprint(bprint)
            else:
                logging.debug('No blueprint to register for plugin %s',
                              pname)
        

OX_HERD_BP = OxHerdBlueprint('ox_herd', __name__, template_folder='templates',
                             static_folder='static', url_prefix='/ox_herd')

