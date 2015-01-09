import os
import provtool
import shutil


def install_profile(profile_path):
    uuid = provtool.uuid(profile_path)
    dst_dir = provtool.DEFAULT_PROVPROF_DIR
    dst_name = "%s.mobileprovision" % (uuid)
    dst_path = os.path.join(dst_dir, dst_name)
    shutil.copyfile(profile_path, dst_path)
    return dst_path
