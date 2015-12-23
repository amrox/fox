import biplist
from fnmatch import fnmatch
import os
import re
import shutil
import logging
from subprocess import check_call, check_output
import sys
from tempfile import mkdtemp
from string import Template

from .defaults import defaults
from .helpers import shellify, run_cmd, puts
from .keychain import add_keychain_cmd, unlock_keychain, find_keychain
from .util import makedirs
from . import provisioningprofile


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




def build_ipa(workspace=None, scheme=None, project=None, target=None,
              config=None, profile=None, identity=None, keychain=None,
              keychain_password=None, output=None, overwrite=False,
              build_dir=None, dsym=False, clean=False, **kwargs):

    if keychain_password is not None:
        if keychain is None:
            keychain = os.path.expanduser("~/Library/Keychains/login.keychain")
        unlock_keychain(keychain, keychain_password)

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

    if keychain is not None:
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
        prov_profile_path = provisioningprofile.find(profile)
        if prov_profile_path is None:
            raise Exception("Profile matching '%s' not found." % (profile))

        build_args.extend([
            'PROVISIONING_PROFILE=%s' % (provisioningprofile.uuid(prov_profile_path))
        ])

    if dsym:
        build_args.extend([
            'DEBUG_INFORMATION_FORMAT=dwarf-with-dsym',
            'DEPLOYMENT_POSTPROCESSING=YES',
            'SEPARATE_STRIP=YES',
            'STRIP_INSTALLED_PRODUCT=YES',
            'DWARF_DSYM_FILE_SHOULD_ACCOMPANY_PRODUCT=YES'
        ])

    ## Just Xcode being Xcode...
    ## http://stackoverflow.com/questions/26516442/how-do-we-manually-fix-resourcerules-plist-cannot-read-resources-error-after
    #build_args.extend([
    #    'CODE_SIGN_RESOURCE_RULES_PATH=$(SDKROOT)/ResourceRules.plist'])

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
            prov_profile_path = os.path.join(defaults['provisioning_profile_dir'])

    build_cmd = shellify(['xcodebuild'] + build_args)
    print build_cmd
    run_cmd(build_cmd)

    # because BUILT_PRODUCTS_DIR from -showBuildSettings can't be trusted if
    # SYMROOT isn't specified...
    if build_dir is not None:
        built_products_dir = build_settings['BUILT_PRODUCTS_DIR']
    else:
        built_products_dir = os.path.join(build_settings['SRCROOT'], 'build',
            '%s-iphoneos' % (build_settings['CONFIGURATION']))

    full_product_name = build_settings['FULL_PRODUCT_NAME']
    full_product_path = os.path.join(built_products_dir, full_product_name)

    # read Info.plist
    info_plist_path = os.path.join(built_products_dir, build_settings['INFOPLIST_PATH'])
    info_plist = biplist.readPlist(info_plist_path)
    build_version = info_plist['CFBundleVersion']
    marketing_version = info_plist['CFBundleShortVersionString']

    tmp_dir = mkdtemp()
    payload_dir = os.path.join(tmp_dir, 'Payload')
    makedirs(payload_dir)

    payload_app_path = os.path.join(payload_dir, os.path.basename(full_product_path))
    shutil.copytree(full_product_path, payload_app_path)

    embedded_prov_profile_path = os.path.join(payload_app_path, 'embedded.mobileprovision')
    src_prov_profile_path = provisioningprofile.find(profile)
    shutil.copyfile(src_prov_profile_path, embedded_prov_profile_path)

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

    makedirs(os.path.dirname(full_output_path))

    # Change working dir so 'Payload' is at the root of the archive.
    # Might be a way to do this with args to zip but I couldn't find it.
    pwd = os.getcwd()
    os.chdir(tmp_dir)
    check_call(['zip', '-qr', full_output_path, 'Payload'])
    os.chdir(pwd)

    if dsym:
        dsym_name = os.path.basename(full_product_path) + '.dSYM'

        ipa_name = os.path.basename(full_output_path)
        output_dir = os.path.dirname(full_output_path)

        dsym_zip_name = os.path.splitext(ipa_name)[0] + '.dSYM.zip'
        dsym_zip_path = os.path.join(output_dir, dsym_zip_name)

        run_cmd(shellify(['zip', '-y', '-r', dsym_zip_path, dsym_name]),
                cwd=built_products_dir)


def extract_info(ipa=None):

    assert ipa

    if not os.path.exists(ipa):
        # TODO: better error
        print "couldn't find ipa"
        sys.exit(1)

    tmp_dir = mkdtemp()

    ## Extract IPA

    check_call(['unzip', '-qq', ipa, '-d', tmp_dir])
    
    payload_path = os.path.join(tmp_dir, 'Payload')
    for file in os.listdir(payload_path):
        if fnmatch(file, '*.app'):
            app_path = os.path.join(payload_path, file)

    # Get Bundle ID from Info.plist

    bundle_id = check_output(["/usr/libexec/PlistBuddy",
        "-c", "Print :CFBundleIdentifier",
        os.path.join(app_path, "Info.plist")]).strip()

    shutil.rmtree(tmp_dir)

    return { 'bundle_id': bundle_id }

   

def resign_ipa(ipa=None, profile=None, identity=None, keychain=None,
        bundle_id=None, entitlements=None, output=None,
        add_resource_rules=False, **kwargs):
    """
    Took work from:

        http://stackoverflow.com/questions/6896029/re-sign-ipa-iphone

    and:

        https://github.com/talk-to/resign-ipa/blob/master/bin/resign-ipa

    """

    assert ipa
    assert profile
    assert identity

    if not os.path.exists(ipa):
        # TODO: better error
        print "couldn't find ipa"
        sys.exit(1)

    tmp_dir = mkdtemp()

    ## Extract IPA

    check_call(['unzip', ipa, '-d', tmp_dir])

    payload_path = os.path.join(tmp_dir, 'Payload')
    for file in os.listdir(payload_path):
        if fnmatch(file, '*.app'):
            app_path = os.path.join(payload_path, file)

    ## Remove Old Code Signature

    shutil.rmtree(os.path.join(app_path, '_CodeSignature'))

    ## Install New Provisioning Profile

    embedded_prov_profile_path = os.path.join(app_path, 'embedded.mobileprovision')
    os.remove(embedded_prov_profile_path)

    src_prov_profile_path = provisioningprofile.find(profile)
    shutil.copyfile(src_prov_profile_path, embedded_prov_profile_path)

    ## Copy and Strip Provisioning Profile of Code Signature Data

    stripped_prov_profile_path = os.path.join(tmp_dir,
    'embedded.mobileprovision.stripped.plist')

    if os.path.exists(stripped_prov_profile_path):
        os.remove(stripped_prov_profile_path)

    check_call(["security", "cms", "-D", "-i",  embedded_prov_profile_path,
        "-o", stripped_prov_profile_path])


    ## Extract the App ID and Team ID for later use

    app_id = run_cmd(shellify(["/usr/libexec/PlistBuddy", "-c",
        "Print:Entitlements:application-identifier",
        stripped_prov_profile_path])).strip()

    team_id = run_cmd(shellify(["/usr/libexec/PlistBuddy", "-c",
        "Print:Entitlements:com.apple.developer.team-identifier",
        stripped_prov_profile_path])).strip()


    ## If bundle id is not supplied, set from extracted

    if bundle_id is None:

        assert app_id.startswith(team_id), "app id doesn't start with team id - this is unexpected"

        bundle_id = app_id[len(team_id) + 1:]  # +1 for '.' between team_id and bundle_id


    ## Set new bundle id

    check_call(["/usr/libexec/PlistBuddy",
        "-c", "Set :CFBundleIdentifier %s" % (bundle_id),
        os.path.join(app_path, "Info.plist")])

    check_call(["cat", os.path.join(app_path, "Info.plist")])

    ## If entitlements are not supplied, extract from provisioning profile

    if entitlements is None:
        entitlements_data = run_cmd(shellify([
            "/usr/libexec/PlistBuddy", "-x", "-c",
            "Print :Entitlements", stripped_prov_profile_path]))

        entitlements = os.path.join(tmp_dir, 'Extracted-Entitlements.plist')
        if os.path.exists(entitlements):
            os.remove(entitlements)

        with open(entitlements, "w") as f:
            f.write(entitlements_data)

        ## experimental, set the keychain access group to just the app

        check_call(["/usr/libexec/PlistBuddy",
            "-c", "Set :keychain-access-groups:0 %s" % (app_id),
            entitlements])

    
    ## Build codesign command

    codesign_args = ['codesign', '-f', '-s', identity,
            '--entitlements', entitlements]

    if add_resource_rules:
        codesign_args.extend(['--resource-rules',
            os.path.join(app_path, 'ResourceRules.plist')])

    if keychain is not None:
        keychain_path = find_keychain(keychain)
        codesign_args.extend(['--keychain', keychain_path])

    codesign_args.extend([app_path])

   
     ## Re-sign!

    codesign_output = check_output(codesign_args)
    puts(codesign_output)

    output_path = os.path.abspath(output)

    ## Rezip

    # Change working dir so 'Payload' is at the root of the archive.
    # Might be a way to do this with args to zip but I couldn't find it.
    pwd = os.getcwd()
    os.chdir(tmp_dir)
    check_call(['zip', '-qr', output_path, 'Payload'])
    os.chdir(pwd)

    shutil.rmtree(tmp_dir)
