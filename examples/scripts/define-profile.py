#!/usr/bin/env python
###
# (C) Copyright (2012-2016) Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
###
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from builtins import range
from future import standard_library
standard_library.install_aliases()
import sys

PYTHON_VERSION = sys.version_info[:3]
PY2 = (PYTHON_VERSION[0] == 2)
if PY2:
    if PYTHON_VERSION < (2, 7, 9):
        raise Exception('Must use Python 2.7.9 or later')
elif PYTHON_VERSION < (3, 4):
    raise Exception('Must use Python 3.4 or later')

import hpOneView as hpov
from pprint import pprint
import re
import json
import hpOneView.profile as profile


def acceptEULA(con):
    # See if we need to accept the EULA before we try to log in
    con.get_eula_status()
    try:
        if con.get_eula_status() is True:
            print('EULA display needed')
            con.set_eula('no')
    except Exception as e:
        print('EXCEPTION:')
        print(e)


def login(con, credential):
    # Login with given credentials
    try:
        con.login(credential)
    except:
        print('Login failed')


def get_server(con, srv, server_id, server_hwt, forcePowerOff):

    sht = None

    if server_id.upper() == 'UNASSIGNED':
        server_hw_types = srv.get_server_hardware_types()
        for ht in server_hw_types:
            if ht['name'] == server_hwt:
                sht = con.get(ht['uri'])
        if not sht:
            print('Error, server hardware type not found')
            sys.exit()
        return None, sht

    # Get handle for named server and power off in necessary
    servers = srv.get_servers()
    located_server = None
    for server in servers:
        ips = server['mpHostInfo']['mpIpAddresses']
        for ip in ips:
            if server_id == server['name'] or server_id == ip['address']:
                located_server = server
                if server['state'] != 'NoProfileApplied':
                    print('\nError: server', server_id, 'already has a profile '
                          'defined or is being monitored\n')
                    sys.exit(1)
                if server['powerState'] == 'On':
                    if forcePowerOff:
                        srv.set_server_powerstate(server, 'Off', force=True)
                    else:
                        print('Error: Server', server_id,
                              ' needs to be powered off')
                        sys.exit(1)
                break
    if not located_server:
        print('Server ', server_id, ' not found')
        sys.exit(1)

    sht = con.get(located_server['serverHardwareTypeUri'])
    if not sht:
        print('Error, server hardware type not found')
        sys.exit()

    return located_server, sht


def define_profile(con, srv, affinity, name, desc, server, sht, boot, bootmode,
                   fw, hide_flexnics, local_storage, conn_list, san_list, bios_list):

    if conn_list:
        # read connection list from file
        conn = json.loads(open(conn_list).read())
    else:
        conn = []

    if san_list:
        # read connection list from file
        san = json.loads(open(san_list).read())
    else:
        san = None

    # Affinity is only supported on Blade Servers so set it to None if the
    # server hardware type model does not match BL
    p = re.compile('.*BL\d.*', re.IGNORECASE)
    match = p.match(sht['model'])
    if not match:
        affinity = None

    if server:
        serverHardwareUri = server['uri']
    else:
        serverHardwareUri = None

    if conn:
        macType = 'Virtual'
        wwnType = 'Virtual'
    else:
        macType = 'Physical'
        wwnType = 'Physical'

    profile = srv.create_server_profile(affinity=affinity,
                                        biosSettings=bios_list,
                                        bootSettings=boot,
                                        bootModeSetting=bootmode,
                                        profileConnectionV4=conn,
                                        description=desc,
                                        firmwareSettingsV3=fw,
                                        hideUnusedFlexNics=hide_flexnics,
                                        localStorageSettingsV3=local_storage,
                                        macType=macType,
                                        name=name,
                                        sanStorageV3=san,
                                        serverHardwareUri=serverHardwareUri,
                                        serverHardwareTypeUri=sht['uri'],
                                        wwnType=wwnType)
    if 'serialNumberType' in profile:
        print('\n\nName:                ', profile['name'])
        print('Description:         ', profile['description'])
        print('Type:                ', profile['type'])
        print('wwnType:             ', profile['wwnType'])
        print('macType:             ', profile['macType'])
        print('serialNumberType:    ', profile['serialNumberType'])
        print('Firmware:')
        print('  manageFirmware:       ', profile['firmware']['manageFirmware'])
        print('  forceInstallFirmware: ', profile['firmware']['forceInstallFirmware'])
        print('  firmwareBaselineUri:  ', profile['firmware']['firmwareBaselineUri'])
        print('Bios:')
        print('  manageBios:         ', profile['bios']['manageBios'])
        print('  overriddenSettings: ', profile['bios']['overriddenSettings'])
        print('Boot:')
        print('  manageBoot:         ', profile['boot']['manageBoot'])
        print('  order:              ', profile['boot']['order'], '\n')
    else:
        pprint(profile_dict)


def main():
    parser = argparse.ArgumentParser(add_help=True,
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description='''
    Define a server profile''')
    parser.add_argument('-a', dest='host', required=True,
                        help='''
    HPE OneView Appliance hostname or IP address''')
    parser.add_argument('-u', dest='user', required=False,
                        default='Administrator',
                        help='''
    HPE OneView Username''')
    parser.add_argument('-p', dest='passwd', required=True,
                        help='''
    HPE OneView Password''')
    parser.add_argument('-c', dest='cert', required=False,
                        help='''
    Trusted SSL Certificate Bundle in PEM (Base64 Encoded DER) Format''')
    parser.add_argument('-y', dest='proxy', required=False,
                        help='''
    Proxy (host:port format''')
    parser.add_argument('-j', dest='domain', required=False,
                        default='Local',
                        help='''
    HPE OneView Authorized Login Domain''')
    parser.add_argument('-n', dest='name',
                        required=True,
                        help='''
    Name of the profile''')
    parser.add_argument('-d', dest='desc',
                        required=False,
                        help='''
    Description for the server profile''')
    parser.add_argument('-af', dest='affinity',
                        required=False, choices=['Bay', 'BayAndServer'],
                        default='Bay',
                        help='''
    This identifies the behavior of the server profile when the server
    hardware is removed or replaced.

        . Bay:  This profile remains with the device bay when the server
                hardware is removed or replaced.

        . BayAndServer This profile is pinned to both the device bay and
          specific server hardware.''')
    parser.add_argument('-f', dest='forcePowerOff',
                        required=False,
                        action='store_true',
                        help='''
    When set, forces power off of target server.
    Avoids error exit if server is up''')
    parser.add_argument('-fw', dest='baseline', required=False,
                        help='''
    SPP Baseline file name. e.g. SPP2013090_2013_0830_30.iso''')
    parser.add_argument('-mb', dest='disable_manage_boot',
                        action='store_true',
                        help='''
    Explicitly DISABLE Boot Order Management. This value is enabled by
    default and required for Connection boot enablement. If this option is
    disabled, then  PXE and FC BfS settings are disabled within the entire
    Server Profile.''')
    parser.add_argument('-bo', dest='boot_order', required=False,
                        nargs='+',
                        help='''
    Defines the order in which boot will be attempted on the available
    devices. Please NOTE the supported boot order is server hardware type
    specific. For Gen7 and Gen8 server hardware the possible values are 'CD',
    'Floppy', 'USB', 'HardDisk', and 'PXE'. For Gen9 BL server hardware in
    Legacy BIOS boot mode, the possible values are 'CD', 'USB', 'HardDisk',
    and 'PXE'. For Gen9 BL server hardware in UEFI or UEFI Optimized boot
    mode, only one value is allowed and must be either 'HardDisk' or 'PXE'.
    For Gen9 DL server hardware in Legacy BIOS boot mode, the possible
    values are 'CD', 'USB', 'HardDisk', and 'PXE'. For Gen9 DL server
    hardware in UEFI or UEFI Optimized boot mode, boot order configuration
    is not supported.

    Server boot order defined as a list separated by spaces. For example:

    Gen7/8 BIOS Default Boot Order:
                            -bo CD Floppy USB HardDisk PXE
    Gen9 Legacy BIOS Boot Order:
                            -bo CD USB HardDisk PXE
    Gen9 UEFI Default Boot Order:
                            -bo HardDisk
    ''')
    parser.add_argument('-cl', dest='conn_list',
                        required=False,
                        help='''
    File with list of connections for this profile in JSON format. This file
    can be created with multiple calls to define-connection-list.py''')
    parser.add_argument('-sl', dest='san_list',
                        required=False,
                        help='''
    File with list of SAN Storage connections for this profile in JSON format.
    This file can be created with multiple calls to
    define-san-storage-list.py''')
    parser.add_argument('-bm', dest='boot_mode', required=False,
                        choices=['UEFI', 'UEFIOptimized', 'BIOS'],
                        default='BIOS',
                        help='''
    Specify the Gen9 Boot Environment.

    Sets the boot mode as one of the following:

        . UEFI
        . UEFIOptimized
        . BIOS

    If you select UEFI or UEFI optimized for an HPE ProLiant DL Gen9 rack
    mount server, the remaining boot setting available is the PXE boot policy.

    For the UEFI or UEFI optimized boot mode options, the boot mode choice
    should be based on the expected OS and required boot features for the
    server hardware. UEFI optimized boot mode reduces the time the system
    spends in POST(Video driver initialization). In order to select the
    appropriate boot mode, consider the following:

        . If a secure boot is required, the boot mode must be set to UEFI
          or UEFI optimized .
        . For operating systems that do not support UEFI (such as DOS, or
          older versions of Windows and Linux), the boot mode must be set
          to BIOS.
        . When booting in UEFI mode, Windows 7, Server 2008, or 2008 R2
          should not be set to UEFIOptimized.''')
    parser.add_argument('-px', dest='pxe', required=False,
                        choices=['Auto', 'IPv4', 'IPv6',
                                 'IPv4ThenIPv6', 'IPv6ThenIPv4'],
                        default='IPv4',
                        help='''
    Controls the ordering of the network modes available to the Flexible
    LOM (FLB); for example, IPv4 and IPv6.

    Select from the following policies:

        . Auto
        . IPv4 only
        . IPv6 only
        . IPv4 then IPv6
        . IPv6 then IPv4

    Setting the policy to Auto means the order of the existing network boot
    targets in the UEFI Boot Order list will not be modified, and any new
    network boot targets will be added to the end of the list using the
    System ROM's default policy.''')
    parser.add_argument('-dn', dest='driveName', required=False,
                        help='''
        The name of the logical drive.''')
    parser.add_argument('-rl', dest='raidlevel', required=False,
                        choices=['NONE', 'RAID0', 'RAID1'],
                        help='''
    Enable local storage to be managed via the server profile by defining the
    RAID level for the logical drive.''')
    parser.add_argument('-pn', dest='physnum', required=False,
                        help='''
    The number of physical drives to be used to build the logical drive.  The
    provided values must be consistent with the selected RAID level and cannot
    exceed the maximum supported number of drives for the selected server
    hardware type.''')
    parser.add_argument('-lb', dest='lboot', required=False,
                        action='store_true',
                        help='''
    Mark the logical drive as NOT bootable''')
    parser.add_argument('-is', dest='init_storage', required=False,
                        action='store_true',
                        help='''
    Indicates whether the local storage controller should be reset to factory
    defaults before applying the local storage settings from the server
    profile.

                  ***************** WARNING *****************

                Setting this will overwrite an existing logical
                 disk if present, and without further warning.

                  ***************** WARNING *****************''')
    parser.add_argument('-hn', dest='hide_flexnics', required=False,
                        action='store_false',
                        help='''
    This setting controls the enumeration of physical functions that do not
    correspond to connections in a profile. Using this flag will SHOW unused
    FlexNICs to the Operating System. Changing this setting may alter the order
    of network interfaces in the Operating System. This option sets the 'Hide
    Unused FlexNICs' to disabled, eight FlexNICs will be enumerated in the
    Operating System as network interfaces for each Flex-10 or FlexFabric
    adapter.  Configuring Fibre Channel connections on a FlexFabric adapter may
    enumerate two storage interfaces, reducing the number of network interfaces
    to six. The default (this option is not selected) enables 'Hide Unused
    FlexNICs' and may suppress enumeration of FlexNICs that do not correspond
    to profile connections. FlexNICs are hidden in pairs, starting with the 4th
    pair. For instance, if the 4th FlexNIC on either physical port corresponds
    to a profile connection, all eight physical functions are enumerated. If a
    profile connection corresponds to the 2nd FlexNIC on either physical port,
    but no connection corresponds to the 3rd or 4th FlexNIC on either physical
    port, only the 1st and 2nd physical functions are enumerated in the
    Operating System.''')
    parser.add_argument('-s', dest='server_id', required=True,
                        help='''
    Server identification. There are multiple ways to specify the server id:

        . Hostname or IP address of the stand-alone server iLO
        . Server Hardware name of a server than has already been imported
          into HPE OneView and is listed under Server Hardware
        . "UNASSIGNED" for creating an unassigned Server Profile''')
    parser.add_argument('-sh', dest='server_hwt', required=False,
                        help='''
    Server hardware type is required for defining an unassigned profile. Note
    the Server Hardware Type must be present in the HPE OneView appliance
    before it can be used. For example, a single server with the specific server
    hardware type must have been added to OneView for that hardware type to
    be used. The example script get-server-hardware-types.py with the -l
    argument can be used to get a list of server hardware types that have
    been imported into the OneView appliance''')
    parser.add_argument('-bl', dest='bios_list',
                        required=False,
                        help='''
    File in JSON format with list of BIOS settings to override for this profile. This file
    can be created with a call to get-bios-options.py''')
    args = parser.parse_args()
    credential = {'authLoginDomain': args.domain.upper(), 'userName': args.user, 'password': args.passwd}

    con = hpov.connection(args.host)
    srv = hpov.servers(con)
    sts = hpov.settings(con)

    if args.proxy:
        con.set_proxy(args.proxy.split(':')[0], args.proxy.split(':')[1])
    if args.cert:
        con.set_trusted_ssl_bundle(args.cert)

    login(con, credential)
    acceptEULA(con)

    # Invert the boolean value
    args.lboot = not args.lboot

    if args.boot_order and args.disable_manage_boot:
        print('Error: Managed Boot must be enabled to define a boot order')
        sys.exit()

    if args.server_id.upper() == 'UNASSIGNED' and not args.server_hwt:
        print('Error: Server Hardware Type must be specified when defining an'
              'unassigned server profile')
        sys.exit()

    server, sht = get_server(con, srv, args.server_id, args.server_hwt,
                             args.forcePowerOff)
    boot, bootmode = profile.make_boot_settings_dict(srv, sht, args.disable_manage_boot,
                                   args.boot_order, args.boot_mode, args.pxe)

    fw_settings = profile.make_firmware_dict(sts, args.baseline)
    local_storage = profile.make_local_storage_dict(sht, args.raidlevel, args.lboot,
                            args.init_storage, args.physnum, args.driveName)
    bios = profile.make_bios_dict(args.bios_list)
    define_profile(con, srv, args.affinity, args.name, args.desc, server, sht,
                   boot, bootmode, fw_settings, args.hide_flexnics,
                   local_storage, args.conn_list, args.san_list, bios)

if __name__ == '__main__':
    import argparse
    sys.exit(main())

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
