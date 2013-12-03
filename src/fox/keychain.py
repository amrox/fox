import os
import shutil
from subprocess import check_output

from .helpers import run_cmd, shellify

USER_KEYCHAIN_DIR = os.path.expanduser("~/Library/Keychains/")


def list_keychains():
    """
    Return a set containing paths to all installed keychains.
    """
    security_output = check_output(['security', 'list-keychains'])
    keychains = set([k.strip()[1:-1] for k in security_output.split('\n') if len(k) > 0])
    return keychains


def find_keychain(keychain_name):
    """
    Tries to find a keychain file using a few methods, and returns it's path if
    found.
    """

    # if it's a path, treat it like a path
    # TODO: better way to test if it's a path?
    if keychain_name[0] in ('~', '/', '.'):
        if os.path.exists(keychain_name):
            return os.path.abspath(keychain_name)

    # add the .keychain extension if necessary
    name, ext = os.path.splitext(keychain_name)
    if len(ext) == 0:
        ext = '.keychain'

    # try to find the keychain file in the user's keychain dir
    filename = '%s%s' % (name, ext)
    user_keychain_path = os.path.join(USER_KEYCHAIN_DIR, filename)
    if os.path.exists(user_keychain_path):
        return user_keychain_path

    return None


def add_keychain_cmd(keychain):
    keychain_path = find_keychain(keychain)
    keychains = list_keychains()
    keychains.add(keychain_path)
    args = ['security', 'list-keychains', '-s']
    args.extend(list(keychains))
    return shellify(args)


def add_keychain(keychain):
    run_cmd(add_keychain_cmd(keychain))


def install_keychain(keychain_path, add=True):
    keychain_file = os.path.basename(keychain_path)
    dest_path = os.path.join(USER_KEYCHAIN_DIR, keychain_file)
    shutil.copyfile(keychain_path, dest_path)
    if add:
        add_keychain(dest_path)
    return dest_path


def unlock_keychain_cmd(keychain, password):
    keychain_path = find_keychain(keychain)
    args = ['security', '-v', 'unlock-keychain', '-p', password,
            keychain_path]
    return shellify(args)


def unlock_keychain(keychain, password):
    run_cmd(unlock_keychain_cmd(keychain, password))
