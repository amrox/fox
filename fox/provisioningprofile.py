import os
import fnmatch
import logging
import plistlib
import shutil

from .defaults import defaults


logger = logging.getLogger(__name__)


def _is_prov_file(filePath):
    return filePath.endswith('.mobileprovision')


def _plist_string_from_prov_file(path):
    beginToken = '<?xml'
    endToken = '</plist>'
    f = open(path)
    data = f.read()
    begin = data.index(beginToken)
    end = data.rindex(endToken) + len(endToken)
    return data[begin:end]


def name(filePath):
    plistString = _plist_string_from_prov_file(filePath)
    plist = plistlib.readPlistFromString(plistString)
    return plist['Name']


def _path(provName, path=None, patternMatch=False):
    if path is None:
        path = defaults['provisioning_profile_dir']

    paths = []
    for f in os.listdir(path):
        if _is_prov_file(f):
            filePath = os.path.join(path, f)
            if not patternMatch and name(filePath) == provName:
                paths.append(filePath)
            elif patternMatch and fnmatch.fnmatch(name(filePath), provName):
                paths.append(filePath)
    return paths


def find_all(input, patternMatch=True):
    """Tries to find a provisioning profile using a few methods, and returns
    it's path if found"""

    # check if it's a valid path first
    if os.path.exists(input):
        return os.path.abspath(input)

    # assume it's a name of a provisioning profile
    paths = _path(input, path=defaults['provisioning_profile_dir'],
            patternMatch=patternMatch)
    if len(paths) == 0:
        return None

    return paths


def find(input, patternMatch=True):
    paths = find_all(input, patternMatch=patternMatch)
    path = paths[0]
    if len(paths) > 1:
        logger.warning('Multiple matches found for "%s", returning first match.'
                % (input))
    return path


def uuid(path):
    fullpath = os.path.expanduser(path)
    if not _is_prov_file(fullpath):
        err = '%s is not a Provisioning Profile' % (fullpath)
        #sys.stderr.write(err)
        raise ValueError(err)  # TODO: ValueError the right kind of exception?
        return None
    plistString = _plist_string_from_prov_file(fullpath)
    plist = plistlib.readPlistFromString(plistString)
    return plist['UUID']


def list(directory=None):

    if directory is None:
        directory = defaults['provisioning_profile_dir']

    l = []
    for f in os.listdir(directory):
        if _is_prov_file(f):
            l.append("%s : '%s'" % (f, name(os.path.join(directory, f))))
    return l


def install_profile(profile_path):
    uuid = uuid(profile_path)
    dst_dir = defaults['provisioning_profile_dir']
    dst_name = "%s.mobileprovision" % (uuid)
    dst_path = os.path.join(dst_dir, dst_name)
    shutil.copyfile(profile_path, dst_path)
    return dst_path
