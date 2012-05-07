import argparse
from clint.textui import puts, indent
from subprocess import call, check_output, Popen
import os, re, sys
import plistlib
from tempfile import mkdtemp
from fnmatch import fnmatch
import shutil

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
    """http://stackoverflow.com/questions/6896029/re-sign-ipa-iphone"""

    prov_profile_path = _find_prov_profile(args.profile)
    if prov_profile_path is None:
        # TODO: better error handling
        print "couldn't find profile"
        sys.exit(1)
   
    build_args = ['xcodebuild', '-sdk', 'iphoneos']
    if args.project is not None:
        build_args.extend(['-project', args.project])
    build_args.extend([
        '-target', args.target, 
        '-config', args.config, 
        'build', 
        'CODE_SIGN_IDENTITY=%s' % (args.identity)])
    build_output = check_output(build_args)
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

def resign(args):
    ipa_path = args.ipa
    if not os.path.exists(ipa_path):
        # TODO: better error
        print "couldn't find ipa"
        sys.exit(1)

    tmp_dir = mkdtemp()
    call(['unzip', ipa_path, '-d', tmp_dir])

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
        keychain_path = os.path.abspath(args.keychain)
        codesign_args.extend(['--keychain', keychain_path])

    codesign_args.extend([app_path])

    codesign_output = check_output(codesign_args)
    puts(codesign_output)

    output_path = os.path.abspath(args.output)

    # Change working dir so 'Payload' is at the root of the archive.
    # Might be a way to do this with args to zip but I couldn't find it.
    pwd = os.getcwd()
    os.chdir(tmp_dir)
    call(['zip', '-qr', output_path, 'Payload'])
    os.chdir(pwd)

    shutil.rmtree(tmp_dir)
    
def main():
    parser = argparse.ArgumentParser(description='')

    subparsers = parser.add_subparsers(title='subcommands',
            description='valid subcommands',
            help='additional help')

    # ipa
    parser_ipa = subparsers.add_parser('ipa', help='ipa help')
    parser_ipa.add_argument('--project', action='store', required=False)
    parser_ipa.add_argument('--target', action='store', required=True)
    parser_ipa.add_argument('--config', action='store', default='Debug', required=False)
    parser_ipa.add_argument('--identity', action='store', required=True)
    parser_ipa.add_argument('--profile', action='store', required=True)
    parser_ipa.set_defaults(func=ipa)

    # resign
    parser_resign = subparsers.add_parser('resign', help='resign help')
    parser_resign.add_argument('--ipa', action='store', required=True)
    parser_resign.add_argument('--identity', action='store', required=True)
    parser_resign.add_argument('--profile', action='store', required=True)
    parser_resign.add_argument('--keychain', action='store', required=False)
    parser_resign.add_argument('--output', action='store', required=True)
    parser_resign.set_defaults(func=resign)

    args = parser.parse_args()
    args.func(args)

