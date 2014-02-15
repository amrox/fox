import argparse
import toml

from .defaults import defaults
from .ipa import build_ipa, resign_ipa
from .keychain import install_keychain, unlock_keychain
from .provisioningprofile import install_profile


def load_fox_config(fox_config_path):
    return toml.load(fox_config_path)


def load_fox_config_from_args(args):
    return load_fox_config(args.config_path)


def get_presets(fox_config, preset_name):
    preset_key = 'preset:%s' % (preset_name)
    return fox_config.get(preset_key)


def call_with_presets(func, args):

    func_args = dict()

    if args.preset is not None:
        fox_config = load_fox_config_from_args(args)
        presets = get_presets(fox_config, args.preset)
        print "Using presets:"
        for (k, v) in presets.iteritems():
            print "   %s = %s" % (k, v)
        func_args = dict(func_args.items() + presets.items())

    func_args = dict(vars(args).items() + func_args.items())

    func(**func_args)


def cmd_ipa(args):
    call_with_presets(build_ipa, args)


def cmd_resign(args):
    call_with_presets(resign_ipa, args)


def cmd_install_keychain(args):
    print install_keychain(args.keychain_path)


def cmd_unlock_keychain(args):
    unlock_keychain(args.keychain, args.password)


def cmd_install_profile(args):
    print install_profile(args.profile_path)


def cmd_debug(args):
    pass


def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-C', action='store', required=False, default=defaults['config_path'],
                        dest='config_path',
                        help="Path to fox config, defaults to '~/.fox'")

    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands',
                                       help='additional help')

    # ipa
    parser_ipa = subparsers.add_parser('ipa', help='Create a signed ipa file.')
    parser_ipa.add_argument('--preset', action='store', required=False)
    parser_ipa.add_argument('--project', action='store', required=False)
    parser_ipa.add_argument('--target', action='store', required=False)
    parser_ipa.add_argument('--workspace', action='store', required=False)
    parser_ipa.add_argument('--scheme', action='store', required=False)
    parser_ipa.add_argument('--config', action='store', default=defaults['build_config'], required=False)
    parser_ipa.add_argument('--identity', action='store', required=False)
    parser_ipa.add_argument('--profile', action='store', required=False)
    parser_ipa.add_argument('--keychain', action='store', required=False)
    parser_ipa.add_argument('--keychain-password', action='store', required=False)
    parser_ipa.add_argument('--output', action='store', default='.', required=False)
    parser_ipa.add_argument('--clean', action='store_true', default=False, required=False)
    parser_ipa.add_argument('--overwrite', action='store_true', default=False, required=False)
    parser_ipa.add_argument('--dsym', action='store_true', default=False, required=False)
    parser_ipa.add_argument('--build_dir', action='store', required=False)
    parser_ipa.set_defaults(func=cmd_ipa)

    # resign
    parser_resign = subparsers.add_parser('resign', help='Resign an ipa file.')
    parser_resign.add_argument('--preset', action='store', required=False)
    parser_resign.add_argument('--ipa', action='store', required=True)
    parser_resign.add_argument('--identity', action='store', required=False)
    parser_resign.add_argument('--profile', action='store', required=False)
    parser_resign.add_argument('--keychain', action='store', required=False)
    parser_resign.add_argument('--output', action='store', required=True)
    parser_resign.set_defaults(func=cmd_resign)

    # install-profile
    parser_install_profile = subparsers.add_parser('install-profile', help='Install a provisioning profile.')
    parser_install_profile.add_argument('profile_path', action='store')
    parser_install_profile.set_defaults(func=cmd_install_profile)

    # install-keychain
    parser_install_keychain = subparsers.add_parser('install-keychain', help='Install a keychain file.')
    parser_install_keychain.add_argument('keychain_path', action='store')
    parser_install_keychain.set_defaults(func=cmd_install_keychain)

    # unlock-keychain
    parser_unlock_keychain = subparsers.add_parser('unlock-keychain', help='Unlock a keychain.')
    parser_unlock_keychain.add_argument('keychain', action='store', help='Keychain name or path')
    parser_unlock_keychain.add_argument('password', action='store', nargs='?',
                                        default='', help='Keychain password')
    parser_unlock_keychain.set_defaults(func=cmd_unlock_keychain)

    parser_debug = subparsers.add_parser('debug', help='debug help')
    parser_debug.set_defaults(func=cmd_debug)

    args = parser.parse_args()
    args.func(args)
