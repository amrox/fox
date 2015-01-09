import biplist
from fnmatch import fnmatch
import os
import provtool
import re
import shutil
import logging
from subprocess import check_call, check_output
import sys
from tempfile import mkdtemp
from string import Template

from .defaults import defaults
from .helpers import join_cmds, shellify, run_cmd, puts
from .keychain import add_keychain_cmd, unlock_keychain_cmd, find_keychain


logger = logging.getLogger(__name__)


def _parse_build_settings(output):

    build_settings = dict()

    for l in output.splitlines():
        # match lines like this:
        #     KEY = VAL
        if re.match(r'\s+.*( = ).*', l):
            key, val = [x.strip() for x in l.split('=')[:2]]
            build_settings[key] = val

    return build_settings


def _determine_target_args(workspace=None, scheme=None, project=None, target=None, **kwargs):
    if workspace is None and project is None:
        raise ValueError("Either workspace or project must be specified.")

    if workspace is not None:
        if scheme is None:
            raise ValueError("If workspace is specified scheme must be also.")
        else:
            return ['-workspace', workspace, '-scheme', scheme]

    if project is not None:
        if target is not None:
            return ['-project', project, '-target', target]
        elif scheme is not None:
            return ['-project', project, '-scheme', scheme]
        else:
            raise ValueError("If project is specified target or scheme must be also.")

    raise NotImplementedError()


def _find_prov_profile(input, patternMatch=True):
    """Tries to find a provisioning profile using a few methods, and returns
    it's path if found"""

    # check if it's a valid path first
    if os.path.exists(input):
        return os.patabspath(input)

    # assume it's a name of a provisioning profile
    paths = provtool.path(input, path=defaults['provisioning_profile_dir'],
            patternMatch=patternMatch)
    if len(paths) == 0:
        return None

    path = paths[0]
    if len(paths) > 1:
        logger.warning('Multiple matches found for "%s", returning first match.'
                % (input))
    return path


def build_ipa(workspace=None, scheme=None, project=None, target=None,
              config=None, profile=None, identity=None, keychain=None,
              keychain_password=None, output=None, overwrite=False,
              build_dir=None, dsym=False, clean=False, **kwargs):

    if keychain_password is not None:
        if keychain is None:
            keychain = os.path.expanduser("~/Library/Keychains/login.keychain")

        keychain_cmd = unlock_keychain_cmd(
            keychain, keychain_password)
    else:
        keychain_cmd = None

    config = config or defaults['build_config']

    build_args = ['-sdk', 'iphoneos']

    if clean:
        build_args.extend(['clean'])

    build_args.extend(['build', '-config', config])
    build_args.extend(_determine_target_args(workspace=workspace, scheme=scheme,
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

    if profile is not None:
        prov_profile_path = _find_prov_profile(profile)
        if prov_profile_path is None:
            # TODO: better error handling
            print "couldn't find profile"
            sys.exit(1)

        build_args.extend([
            'PROVISIONING_PROFILE=%s' % (provtool.uuid(prov_profile_path))
        ])

    build_settings_cmd = ['xcodebuild', '-showBuildSettings'] + build_args
    print shellify(build_settings_cmd)
    build_settings_output = check_output(build_settings_cmd)
    build_settings = _parse_build_settings(build_settings_output)

    if profile is None:
        # Read the profile from the build settings
        prov_profile_uuid = build_settings.get('PROVISIONING_PROFILE')
        if prov_profile_uuid is None or prov_profile_uuid.strip() == '':
            print "couldn't find profile in build settings"
            sys.exit(1)
        else:
            # TODO: clean this up
            file_name = '%s.mobileprovision' % (prov_profile_uuid)
            prov_profile_path = os.path.join(provtool.DEFAULT_PROVPROF_DIR, file_name)

    build_cmd = shellify(['xcodebuild'] + build_args)
    if keychain_cmd is not None:
        # unlocking keychain in the same shell to try to prevent
        # "User Interaction is Not Allowed" errors
        build_cmd = join_cmds(keychain_cmd, build_cmd)

    print build_cmd
    run_cmd(build_cmd)

    built_products_dir = build_settings['BUILT_PRODUCTS_DIR']
    full_product_name = build_settings['FULL_PRODUCT_NAME']
    full_product_path = os.path.join(built_products_dir, full_product_name)

    # read Info.plist
    info_plist_path = os.path.join(built_products_dir, build_settings['INFOPLIST_PATH'])
    info_plist = biplist.readPlist(info_plist_path)
    build_version = info_plist['CFBundleVersion']
    marketing_version = info_plist['CFBundleShortVersionString']

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

    app_name = os.path.splitext(full_product_name)[0]
    output_template_vars = {
        'app_name': app_name,
        'marketing_version': marketing_version,
        'build_version': build_version,
        'config': config,
    }

    if output is None:
        output = '.'  # default to current directory and ipa format

    substituted_output = Template(output).substitute(output_template_vars)
    output_path = os.path.abspath(substituted_output)

    if os.path.isdir(output_path):
        ipa_name = Template(defaults['ipa_output_template']).substitute(output_template_vars)
        full_output_path = os.path.join(output_path, ipa_name)
    else:
        full_output_path = output_path

    if overwrite and os.path.exists(full_output_path):
        os.remove(full_output_path)

    src_ipa_path = full_product_path[:-3] + 'ipa'
    shutil.move(src_ipa_path, full_output_path)

    if dsym:
        dsym_name = os.path.basename(full_product_path) + '.dSYM'

        ipa_name = os.path.basename(full_output_path)
        output_dir = os.path.dirname(full_output_path)

        dsym_zip_name = os.path.splitext(ipa_name)[0] + '.dSYM.zip'
        dsym_zip_path = os.path.join(output_dir, dsym_zip_name)

        run_cmd(shellify(['zip', '-y', '-r', dsym_zip_path, dsym_name]),
                cwd=built_products_dir)


def resign_ipa(ipa=None, profile=None, identity=None, keychain=None,
               output=None, **kwargs):
    """http://stackoverflow.com/questions/6896029/re-sign-ipa-iphone"""

    assert ipa
    assert profile
    assert identity

    if not os.path.exists(ipa):
        # TODO: better error
        print "couldn't find ipa"
        sys.exit(1)

    tmp_dir = mkdtemp()
    check_call(['unzip', ipa, '-d', tmp_dir])

    payload_path = os.path.join(tmp_dir, 'Payload')
    for file in os.listdir(payload_path):
        if fnmatch(file, '*.app'):
            app_path = os.path.join(payload_path, file)

    shutil.rmtree(os.path.join(app_path, '_CodeSignature'))

    embedded_prov_profile_path = os.path.join(app_path, 'embedded.mobileprovision')
    os.remove(embedded_prov_profile_path)

    src_prov_profile_path = _find_prov_profile(profile)
    shutil.copyfile(src_prov_profile_path, embedded_prov_profile_path)

    codesign_args = ['codesign', '-f',
                     '-s', identity,
                     '--resource-rules',
                     os.path.join(app_path, 'ResourceRules.plist'),
                     '--entitlements',
                     os.path.join(app_path, 'Entitlements.plist')]

    if keychain is not None:
        keychain_path = find_keychain(keychain)
        codesign_args.extend(['--keychain', keychain_path])

    codesign_args.extend([app_path])

    codesign_output = check_output(codesign_args)
    puts(codesign_output)

    output_path = os.path.abspath(output)

    # Change working dir so 'Payload' is at the root of the archive.
    # Might be a way to do this with args to zip but I couldn't find it.
    pwd = os.getcwd()
    os.chdir(tmp_dir)
    check_call(['zip', '-qr', output_path, 'Payload'])
    os.chdir(pwd)

    shutil.rmtree(tmp_dir)
