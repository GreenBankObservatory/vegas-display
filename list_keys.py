#! /usr/bin/env python
######################################################################
#
#  list_keys.py - lists all the keys being published by a device.
#
#  Usage:
#      list_keys.py <device> [subdevice]
#
#  For example:
#      list_keys.py Undulator UndulatorB
#      list_keys.py Chomper
#
#  It will start printing out the received data.
#
#  Copyright (C) 2012 Associated Universities, Inc. Washington DC, USA.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#  Correspondence concerning GBT software should be addressed as follows:
#  GBT Operations
#  National Radio Astronomy Observatory
#  P. O. Box 2
#  Green Bank, WV 24944-0002 USA
#
######################################################################

import zmq
import argparse
from DataStreamUtils import get_service_endpoints, get_directory_endpoints


def main():
    """ main method """
    # get the arguments: major [minor]
    parser = argparse.ArgumentParser(
        description='Obtain published keys from a named device')
    parser.add_argument('major', metavar='maj', nargs=1,
                        help='The major device name.')
    parser.add_argument('minor', metavar='min', nargs='?', default='',
                        help='The minor device name.')
    args = parser.parse_args()
    major = args.major[0]

    # Devices that are not subdevices (usually?) have same major and
    # minor device names, and may be specified with only one name.
    if not args.minor:
        minor = major
    else:
        minor = args.minor

    context = zmq.Context(1)
    req_url = get_directory_endpoints('request')
    url = get_service_endpoints(context, req_url, major, minor, 1)[0] # the TCP url is 0
    request = context.socket(zmq.REQ)
    request.linger = 0

    request.connect(url)
    parts = ["LIST", major, minor]
    request.send_multipart(parts)

    buffers = request.recv_multipart()

    # get rid of 'END', and sort.
    buffers.pop()
    buffers.sort()

    # print keys.
    for buf in buffers:
        print buf

    request.close()

if __name__ == "__main__":
    main()
