import argparse
import os
import plistlib
import re
import shutil
import sys
import toml
from fnmatch import fnmatch
from subprocess import check_call, check_output
from tempfile import mkdtemp

from .helpers import join_cmds, shellify, run_cmd, puts
from .keychain import add_keychain_cmd, unlock_keychain_cmd, install_keychain, unlock_keychain, find_keychain
from .provisioningprofile import install_profile

#### stolen from provtool https://github.com/mindsnacks/provtool

DEFAULT_PROVPROF_DIR = os.path.expanduser('~/Library/MobileDevice/Provisioning Profiles')
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.fox")
DEFAULT_BUILD_CONFIG = "Debug"


def is_prov_profile(filePath):
    return filePath.endswith('.mobileprovision')


def plist_string_from_prov_profile_path(path):
    beginToken = '<?xml'
    endToken = '</plist>'
    f = open(path)
    data = f.read()
    begin = data.index(beginToken)
    end = data.rindex(endToken) + len(endToken)
    return data[begin:end]


def name_from_prov_profile_path(filePath):
    plistString = plist_string_from_prov_profile_path(filePath)
    plist = plistlib.readPlistFromString(plistString)
    return plist['Name']


def find_prov_profile_by_name(name, dir=DEFAULT_PROVPROF_DIR):
    if not os.path.exists(dir):
        return None
    for f in os.listdir(dir):
        if is_prov_profile(f):
            path = os.path.join(dir, f)
            if name == name_from_prov_profile_path(path):
                return path
    return None

#### end provtool


def _find_prov_profile(input):
    """Tries to find a provisioning profile using a few methods, and returns
    it's path if found"""

    # check if it's a valid path first
    if os.path.exists(input):
        return os.patabspath(input)

    # assume it's a name of a provisioning profile
    path = find_prov_profile_by_name(input)

    return path


def determine_target_args(workspace=None, scheme=None, project=None, target=None, **kwargs):
    if workspace is None and project is None:
        raise ValueError("Either workspace or project must be specified.")

    if workspace is not None:
        if scheme is None:
            raise ValueError("If workspace is specified scheme must be also.")
        else:
            return ['-workspace', workspace, '-scheme', scheme]

    if project is not None:
        if target is None:
            raise ValueError("If project is specified target must be also.")
        else:
            return ['-project', project, '-target', target]

    raise NotImplementedError()


def get_build_settings(workspace=None, scheme=None, project=None, target=None, config=None):

    config = config or DEFAULT_BUILD_CONFIG

    cmd = ['xcodebuild', '-showBuildSettings', "-config", config]
    cmd.extend(determine_target_args(workspace=workspace, scheme=scheme,
                                     project=project, target=target))

    build_settings = dict()
    output = check_output(cmd)
    for l in output.splitlines():
        # match lines like this:
        #     KEY = VAL
        if re.match(r'\s+.*( = ).*', l):
            key, val = [x.strip() for x in l.split('=')[:2]]
            build_settings[key] = val

    return build_settings


def build_ipa(workspace=None, scheme=None, project=None, target=None,
              config=None, profile=None, identity=None, keychain=None,
              keychain_password=None, output=None, overwrite=False, build_dir=None,
              **kwargs):

    prov_profile_path = _find_prov_profile(profile)
    if prov_profile_path is None:
        # TODO: better error handling
        print "couldn't find profile"
        sys.exit(1)

    build_settings = get_build_settings(workspace=workspace, scheme=scheme,
                                        project=project, target=target)

    if keychain is not None and keychain_password is not None:
        keychain_cmd = unlock_keychain_cmd(
            keychain, keychain_password)
    else:
        keychain_cmd = None

    build_args = ['xcodebuild', '-sdk', 'iphoneos', 'build']
    build_args.extend(determine_target_args(workspace=workspace, scheme=scheme,
                                            project=project, target=target))

    if identity is not None:
        build_args.extend([
            'CODE_SIGN_IDENTITY=%s' % (identity)
        ])

    if keychain_cmd is not None:
        run_cmd(add_keychain_cmd(keychain))

        build_args.extend([
            'OTHER_CODE_SIGN_FLAGS=--keychain=%s' %
            find_keychain(keychain)
        ])

    if build_dir is not None:
        build_args.extend([
            'SYMROOT=%s' % (os.path.realpath(build_dir))
        ])

    build_cmd = shellify(build_args)
    if keychain_cmd is not None:
        # unlocking keychain in the same shell to try to prevent
        # "User Interaction is Not Allowed" errors
        build_cmd = join_cmds(keychain_cmd, build_cmd)

    print build_cmd
    run_cmd(build_cmd)

    built_products_dir = build_settings['BUILT_PRODUCTS_DIR']
    full_product_name = build_settings['FULL_PRODUCT_NAME']
    full_product_path = os.path.join(built_products_dir, full_product_name)

    # unlock the keychain again
    if keychain_password is not None:
        run_cmd(keychain_cmd)

    package_args = ['xcrun', '-v',
                    '-sdk', 'iphoneos',
                    'PackageApplication', full_product_path,
                    '--embed', prov_profile_path]
    if identity is not None:
        package_args.extend([
            '--sign', identity,
        ])
    package_cmd = shellify(package_args)
    print package_cmd

    if keychain_cmd is not None:
        package_cmd = join_cmds(keychain_cmd, package_cmd)

    check_call(package_cmd, shell=True)

    # shutil.move has some odd behavior. If you specifiy a full absolute path as
    # the destination, and the path exists, it will overwrite it. If you
    # specify a directory as the output path, and a file in that directory
    # exists, it will fail. We try to preserve that behavior.

    full_ipa_path = full_product_path[:-3] + 'ipa'
    output_path = os.path.abspath(output)
    full_output_path = output_path

    if os.path.isdir(output_path):
        full_output_path = os.path.join(output_path, os.path.basename(full_ipa_path))

    if overwrite and os.path.exists(full_output_path):
        os.remove(full_output_path)

    shutil.move(full_ipa_path, output_path)


def resign(args):
    """http://stackoverflow.com/questions/6896029/re-sign-ipa-iphone"""

    ipa_path = args.ipa
    if not os.path.exists(ipa_path):
        # TODO: better error
        print "couldn't find ipa"
        sys.exit(1)

    tmp_dir = mkdtemp()
    check_call(['unzip', ipa_path, '-d', tmp_dir])

    payload_path = os.path.join(tmp_dir, 'Payload')
    for file in os.listdir(payload_path):
        if fnmatch(file, '*.app'):
            app_path = os.path.join(payload_path, file)

    shutil.rmtree(os.path.join(app_path, '_CodeSignature'))

    embedded_prov_profile_path = os.path.join(app_path, 'embedded.mobileprovision')
    os.remove(embedded_prov_profile_path)

    src_prov_profile_path = _find_prov_profile(args.profile)
    shutil.copyfile(src_prov_profile_path, embedded_prov_profile_path)

    codesign_args = ['codesign', '-f',
                     '-s', args.identity,
                     '--resource-rules',
                     os.path.join(app_path, 'ResourceRules.plist'),
                     '--entitlements',
                     os.path.join(app_path, 'Entitlements.plist')]

    if args.keychain is not None:
        keychain_path = find_keychain(args.keychain)
        codesign_args.extend(['--keychain', keychain_path])

    codesign_args.extend([app_path])

    codesign_output = check_output(codesign_args)
    puts(codesign_output)

    output_path = os.path.abspath(args.output)

    # Change working dir so 'Payload' is at the root of the archive.
    # Might be a way to do this with args to zip but I couldn't find it.
    pwd = os.getcwd()
    os.chdir(tmp_dir)
    check_call(['zip', '-qr', output_path, 'Payload'])
    os.chdir(pwd)

    shutil.rmtree(tmp_dir)


def load_fox_config(fox_config_path):
    return toml.load(fox_config_path)


def load_fox_config_from_args(args):
    return load_fox_config(args.config_path)


def get_presets(fox_config, preset_name):
    preset_key = 'preset:%s' % (preset_name)
    return fox_config.get(preset_key)


def cmd_ipa(args):

    build_ipa_args = dict()

    if args.preset is not None:
        fox_config = load_fox_config_from_args(args)
        presets = get_presets(fox_config, args.preset)
        print "Using presets:"
        for (k, v) in presets.iteritems():
            print "   %s = %s" % (k, v)
        build_ipa_args = dict(build_ipa_args.items() + presets.items())

    build_ipa_args = dict(vars(args).items() + build_ipa_args.items())

    build_ipa(**build_ipa_args)


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
    parser.add_argument('-C', action='store', required=False, default=DEFAULT_CONFIG_PATH,
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
    parser_ipa.add_argument('--config', action='store', default=DEFAULT_BUILD_CONFIG, required=False)
    parser_ipa.add_argument('--identity', action='store', required=False)
    parser_ipa.add_argument('--profile', action='store', required=False)
    parser_ipa.add_argument('--keychain', action='store', required=False)
    parser_ipa.add_argument('--keychain-password', action='store', required=False)
    parser_ipa.add_argument('--output', action='store', default='.', required=False)
    parser_ipa.add_argument('--overwrite', action='store_true', default=False, required=False)
    parser_ipa.add_argument('--build_dir', action='store', required=False)
    parser_ipa.set_defaults(func=cmd_ipa)

    # resign
    parser_resign = subparsers.add_parser('resign', help='Resign an ipa file.')
    parser_resign.add_argument('--ipa', action='store', required=True)
    parser_resign.add_argument('--identity', action='store', required=True)
    parser_resign.add_argument('--profile', action='store', required=True)
    parser_resign.add_argument('--keychain', action='store', required=False)
    parser_resign.add_argument('--output', action='store', required=True)
    parser_resign.set_defaults(func=resign)

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
