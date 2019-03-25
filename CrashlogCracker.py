#!/usr/bin/python

import re
import argparse
import os.path
from collections import namedtuple
import uuid
import commands
from StringIO import StringIO

# Definition refered from crashlog.py
PARSE_MODE_NORMAL = 0
PARSE_MODE_IMAGES = 2

# A simplified version of DarwinImage class
DarwinImage = namedtuple('DarwinImage', 'text_addr_lo text_addr_hi identifier version uuid path')
MachOBinary = namedtuple('MachOBinary', 'uuid version path')

verbose_mode = False

def darwin_image_str(image):
    ''' 
    Example:
    0x104488000 - 0x1044a7fff ZipArchive arm64  <5b2aa73e69f735c588de50c96524a632> 
    /var/containers/Bundle/Application/B8D077AF-2EC6-47F9-9367-C8DD91E14BA2/Telis.app/
    Frameworks/ZipArchive.framework/ZipArchive
    '''
    return "{} - {} {} {} <{}> {}\n".format(image.text_addr_lo, image.text_addr_hi, 
        image.identifier, image.version, image.uuid.hex, image.path)

class Archive:
    dsym_regex = re.compile('UUID: ([-0-9a-fA-F]+) \((.*?)\) (.*)')

    @staticmethod
    def insert_mach_o_binary(path, dic):
        global verbose_mode

        shell_path = path.replace(" ", "\\ ")
        record = commands.getoutput("xcrun dwarfdump --uuid " + shell_path)
        for line in StringIO(record):
            record_match = Archive.dsym_regex.search(line)
            if record_match is None:
                continue
            record = MachOBinary(
                uuid.UUID(record_match.group(1)), 
                record_match.group(2), 
                record_match.group(3))
            identifier = list(os.path.split(record.path))[-1]
            key = "{}-{}".format(identifier, record.version)
            if verbose_mode:
                print("Read MachO library from archive. {}".format(record))
            dic[key] = record

    def __init__(self, archive):
        # self.dsymsdic = {}
        self.binaries_dic = {}
        abs_archive = os.path.abspath(archive)

        # dsymsdir = os.path.join(abs_archive, "dSYMs")
        # for dsym in os.listdir(dsymsdir):
        #     dsym_path = os.path.join(dsymsdir, dsym)
        #     Archive.insert_mach_o_binary(dsym_path, self.dsymsdic)

        applications_dir = os.path.join(abs_archive, "Products/Applications/")
        try:
            app_dir_name = os.listdir(applications_dir)[0]
        except:
            exception_description = "{} is not a valid xcarchive.".format(args.archive)
            raise ValueError(exception_description)
        app_dir = os.path.join(applications_dir, app_dir_name)
        print("Found app at {}".format(app_dir))

        app_name = app_dir_name[:-4] # drop '.app'
        Archive.insert_mach_o_binary(os.path.join(app_dir, app_name), self.binaries_dic)
        frameworks_dir = os.path.join(app_dir, "Frameworks")
        for framework_file in os.listdir(frameworks_dir):
            if framework_file.endswith(".dylib"):
                dylib_path = os.path.join(frameworks_dir, framework_file)
                Archive.insert_mach_o_binary(dylib_path, self.binaries_dic)
            elif framework_file.endswith(".framework"):
                framework = framework_file[:-10] # drop ".framework"
                framework_path = os.path.join(frameworks_dir, framework_file, framework)
                Archive.insert_mach_o_binary(framework_path, self.binaries_dic)

    # def dsym_for_identifier(self, identifier, version):
    #     key = "{}-{}".format(identifier, version)
    #     return self.dsymsdic.get(key)

    def binary_for_identifier(self, identifier, version):
        key = "{}-{}".format(identifier, version)
        return self.binaries_dic.get(key)

def load_system_symbols(versionline):
    version_regex = re.compile('([\d\.]+) \(([0-9A-F]+)\)')
    version_match = version_regex.search(versionline)
    if not version_match:
        print('Warning: Failed to read version info. Skip convert system library references.')
        return
    system_symbols_path = os.path.expanduser('~/Library/Developer/Xcode/iOS DeviceSupport/')
    versionlist = os.listdir(system_symbols_path)
    full_version_string = version_match.group(0)
    if full_version_string not in versionlist:
        print("Warning: No matched system symbols found. Consider connect to an iOS {} "
            "device to retrive system symbols. Or you can try using symbols resource in "
            "this repo: https://github.com/Zuikyo/iOS-System-Symbols"
            .format(version_match.group(0)))
        return
    return os.path.join(system_symbols_path, full_version_string, "Symbols")

def handle_arguments():
    global verbose_mode

    parser = argparse.ArgumentParser("crashlogcracker")
    parser.add_argument("crashlog", 
        help="The crashlog file you want to crack on.", 
        type=argparse.FileType('r'))
    parser.add_argument("--archive", 
        help="An .xcarchive file corresponding to the crashlog.", required=True)
    parser.add_argument("-o", "--output", 
        help="Output crashlog path. Will use \"converted.\" + original crashlog's name if not sepcified.", 
        type=argparse.FileType('w+'))
    parser.add_argument("--verbose", action='store_true')
    args = parser.parse_args()
    if not os.path.isdir(args.archive):
        exception_description = "{} is not a valid xcarchive.".format(args.archive)
        raise ValueError(exception_description)
    output = args.output
    if not output:
        basename, filename = os.path.split(args.crashlog.name)
        outputpath = os.path.join(basename, "converted." + filename)
        output = open(outputpath, "w+")
    output.truncate()
    verbose_mode = args.verbose
    if verbose_mode:
        print("Using verbose mode. Will print all modification.")
    return args.crashlog, args.archive, output

def main():
    global verbose_mode

    crashlog, archivepath, output = handle_arguments()
    archive = Archive(archivepath)

    image_regex_uuid = re.compile(
        '(0x[0-9a-fA-F]+)[- ]+(0x[0-9a-fA-F]+) +[+]?([^ ]+) +([^<]+)<([-0-9a-fA-F]+)> (.*)')

    parse_mode = PARSE_MODE_NORMAL
    system_symbols_path = None
    for line in crashlog:
        if line == "\n":
            parse_mode = PARSE_MODE_NORMAL
            output.write("\n")
        elif parse_mode == PARSE_MODE_NORMAL:
            if line.startswith('Binary Images:'):
                parse_mode = PARSE_MODE_IMAGES
            elif line.startswith('OS Version:'):
                system_symbols_path = load_system_symbols(line)
            output.write(line)
        elif parse_mode == PARSE_MODE_IMAGES:
            image_match = image_regex_uuid.search(line)
            if image_match:
                image = DarwinImage(image_match.group(1),
                                    image_match.group(2),
                                    image_match.group(3).strip(),
                                    image_match.group(4).strip(),
                                    uuid.UUID(image_match.group(5)),
                                    image_match.group(6))
                record = archive.binary_for_identifier(image.identifier, image.version)
                if record:
                    new_image = DarwinImage(image.text_addr_lo,
                                            image.text_addr_hi,
                                            image.identifier,
                                            image.version,
                                            record.uuid,
                                            record.path)
                    output.write(darwin_image_str(new_image))
                    if verbose_mode:
                        print("Replaced image {} with local library of path: {}, uuid: ".format(image, record.path, record.uuid))
                elif system_symbols_path is not None and (
                    image.path.startswith('/System') or image.path.startswith('/usr')):
                    local_symbol_path = "{}{}".format(system_symbols_path, image.path)
                    new_image = DarwinImage(image.text_addr_lo,
                                            image.text_addr_hi,
                                            image.identifier,
                                            image.version,
                                            image.uuid,
                                            local_symbol_path)
                    output.write(darwin_image_str(new_image))
                    if verbose_mode:
                        print("Replaced system image {} with local system library of path: {}".format(image, local_symbol_path))
                else:
                    output.write(line)
            else:
                print "error: image regex failed for: %s" % line
    print("crashlog rebuild a s {}".format(output.name))
    
if __name__ == '__main__':
    main()