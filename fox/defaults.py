# -*- coding: utf-8 -*-

import os

defaults = dict()

defaults['config_path'] = os.path.expanduser("~/.fox")
defaults['provisioning_profile_dir'] = os.path.expanduser('~/Library/MobileDevice/Provisioning Profiles')
defaults['build_config'] = 'Debug'
defaults['ipa_output_template'] = '${app_name}_${marketing_version}_${build_version}_${config}.ipa'
