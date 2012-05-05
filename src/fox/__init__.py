import argparse
from clint.textui import puts, indent
from subprocess import call, check_output
import os, re, sys
import plistlib

#### stolen from provtool https://github.com/mindsnacks/provtool

DEFAULT_PROVPROF_DIR = os.path.expanduser('~/Library/MobileDevice/Provisioning Profiles')

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
    for f in os.listdir(dir):
        if is_prov_profile(f):
            path = os.path.join(dir, f)
            if name == name_from_prov_profile_path(path):
                return path
    return None

#### end provtool

def _parse_setenv_var(var, text):
    return re.search(r'(setenv %s )(.*)' % var, text).group(2)

def _find_prov_profile(input):
    """Tries to find a provisioning profile using a few methods, and returns
    it's path if found"""

    # check if it's a valid path first
    if os.path.exists(input):
        return os.path.abspath(input)

    # assume it's a name of a provisioning profile
    path = find_prov_profile_by_name(input)

    return path

def ipa(args):
    prov_profile_path = _find_prov_profile(args.profile)
    if prov_profile_path is None:
        # TODO: better error handling
        print "couldn't find profile"
        sys.exit(1)
    
    build_output = check_output(
            ['xcodebuild', 
                '-sdk', 'iphoneos', 
                '-target', args.target, 
                '-config', args.config, 
                'build', 
                'CODE_SIGN_IDENTITY=%s' % (args.identity)])
    puts(build_output)

    built_products_dir = _parse_setenv_var('BUILT_PRODUCTS_DIR', build_output)
    full_product_name = _parse_setenv_var('FULL_PRODUCT_NAME', build_output)
    full_product_path = os.path.join(built_products_dir, full_product_name)

    package_output = check_output(
            ['xcrun', '-v', 
                '-sdk', 'iphoneos',
                'PackageApplication', full_product_path,
                '--sign', args.identity,
                '--embed', prov_profile_path]
            )
    puts(package_output)


def main():
    parser = argparse.ArgumentParser(description='')

    subparsers = parser.add_subparsers(title='subcommands',
            description='valid subcommands',
            help='additional help')

    # ipa
    parser_ipa = subparsers.add_parser('ipa', help='ipa help')
    parser_ipa.add_argument('--target', action='store', required=True)
    parser_ipa.add_argument('--identity', action='store', required=True)
    parser_ipa.add_argument('--profile', action='store', required=True)
    #parser_ipa.add_argument('--project', action='store', required=False)
    parser_ipa.add_argument('--config', action='store', default='Debug', required=False)
    parser_ipa.set_defaults(func=ipa)

    # resign
    #parser_resign = subparsers.add_parser('resign', help='resign help')

    args = parser.parse_args()
    args.func(args)

