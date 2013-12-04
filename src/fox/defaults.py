# -*- coding: utf-8 -*-

"""
zinc.defaults
~~~~~~~~~~~~~

This module provides the Zinc configuration defaults.

Configurations:
:build_config: The default build configuration if none is specified.
:provisioning_profile_dir: The directory where provisioning profiles should be stored.
:config_path: The path to the fox config if none is specified.
"""

import os

defaults = dict()

defaults['config_path'] = os.path.expanduser("~/.fox")
defaults['provisioning_profile_dir'] = os.path.expanduser('~/Library/MobileDevice/Provisioning Profiles')
defaults['build_config'] = 'Debug'
