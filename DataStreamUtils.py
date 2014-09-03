######################################################################
#
#  DataStreamUtils.py - utilities to help data streaming clients get
#  to the data streaming services.
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

import os
import zmq
import ConfigParser
import re

from request_pb2 import *
from PBDataDescriptor_pb2 import *

NS_REGISTER = 0
NS_REQUEST = 1
NS_PUBLISHER = 2

SERV_PUBLISHER = 0
SERV_SNAPSHOT = 1
SERV_CONTROL = 2

def get_service_endpoints(context, req_url, device, subdevice, interface = -1):
    """Request 0MQ endpoint URLs from the YgorDirectory service.  The device
    and subdevice are used to query the directory for the URLs.  Each
    device will have 3 categories of URLs. 0: the publishing URLs; 1:
    the snapshot URL; 2: the control URL.  If the interface is specified
    (via the 'interface' parameter), the return value is a list of URLs
    for the interface specified.  If not, it is a list of lists of URLs
    for all 3 interfaces.

    """

    request = context.socket(zmq.REQ)
    request.connect(req_url)
    reqb = PBRequestService()
    reqb.major = device
    reqb.minor = subdevice

    if interface > -1 and interface < 3:
        reqb.interface = interface

    request.send(reqb.SerializeToString())
    reply = request.recv()
    reqb.ParseFromString(reply)
    request.close()

    if interface == 0:
        return reqb.publish_url
    if interface == 1:
        return reqb.snapshot_url
    if interface == 2:
        return reqb.control_url
    return [reqb.publish_url, reqb.snapshot_url, reqb.control_url]

def get_directory_endpoints(interface = None):
    """
    get_directory_endpoints(interface)

    Returns the endpoint URL(s) for the YgorDirectory 0MQ name
    service.  YgorDirectory provides 3 interfaces: 'register', which
    allows a service to register itself with the name service;
    'request', which allows a client to request a registered service
    by name; and 'publisher' which any subscriber may use to track
    YgorDirectory events (server up/down, new service registered,
    etc.).  Caller may specify which of these it wants, in which case
    the function returns the URL as a string; or request all of them
    if the 'interface' parameter is omitted, in which case the return
    value is a list of the URLs, in the order given above.
    """

    ygor_telescope = os.getenv("YGOR_TELESCOPE")

    if not ygor_telescope:
        raise Exception("YGOR_TELESCOPE is not defined!")

    interfaces = ['register', 'request', 'publisher']
    # read the config file for the YgorDirectory request URL
    config = ConfigParser.ConfigParser()
    config.readfp(open(ygor_telescope + "/etc/config/ZMQEndpoints.conf"))

    if interface and interface in interfaces:
        return config.get('YgorDirectory', interface)

    return [config.get('YgorDirectory', p) for p in interfaces]


def subscribe_to_key(snap, sub, key):
    """
    subscribe_to_key(snap, sub, key)

    Subscribes to the key 'key' using zmq socket 'sub', then retrieves
    a snapshot of the key's value from the server using the zmq socket
    'snap'.  The snapshot solves the late-joiner problem.

    returns a list [PBDataDescriptor_pb2,...]
    """
    # first subscribe.  It does no harm if the key is bogus.
    sub.setsockopt(zmq.SUBSCRIBE, key)
    # next, send a request for the latest value(s) snapshot
    snap.send(key)
    rl = []
    rl = snap.recv_multipart()
    el = len(rl)

    if el == 1:  # Got an error
        if rl[0] == "E_NOKEY":
            raise Exception("No key/value pair %s found on server!" % (key))
    if el > 1:
        # first element is the key
        # the following elements are the values
        rval = []

        for i in range(1, el):
            df = PBDataField()
            df.ParseFromString(rl[i])
            rval.append(df)

    return rval

def get_data_snapshot(key, sock = None):
    """ Obtains and returns one snapshot of data """

    if sock:
        snap = sock
        close_socket = False
    else:
        # sockets to get current snapshot of values
        context = zmq.Context(1)

        try:
            major, minor, dtype, name = re.split("[.:]", key)
        except ValueError:
            major, minor, dtype = re.split("[.:]", key)

        directory_url = get_directory_endpoints("request")
        device_url, _, _ = get_service_endpoints(context, directory_url,
                                                 major, minor, SERV_SNAPSHOT)

        snap = context.socket(zmq.REQ)
        snap.linger = 0
        snap.connect(device_url)
        close_socket = True

    snap.send(key)
    rl = []
    rl = snap.recv_multipart()

    if close_socket: # our socket, we should close.
        snap.close()

    el = len(rl)

    if el == 1:  # Got an error
        if rl[0] == "E_NOKEY":
            print "No key/value pair %s found on server!" % (key)
            return None
    elif el > 1:
        # first element is the key
        # the following elements are the values
        df = PBDataField()
        df.ParseFromString(rl[1])
        return df
    else:
        return None

def str_list(l):
    """Given the list 'l', produces a string with each element of 'l'
    stringified and separated by a comma::

       l = [1, 2, 3]
       sl = str_list(l)
       print sl
       '1,2,3'

    l: The list of values. Each element must be convertible to a string
    via 'str()'.

    """
    the_string = ""

    for i in l:
        the_string += "%s," % (str(i))

    return the_string[:-1]

def print_parameter_value(pb, spaces = ""):
    """Prints the parameter value, given a PBDataField. Since the
    PBDataField can recursively hold other PBDataFields, this function
    will run through the descriptor printing every appropriate level.

    pb: The PBDataField to pring

    spaces: The number of spaces to print before printing the 'pb'

    fields. Normally not used by the caller, this is used by the

    function itself as it calls itself recursively.

    """
    t = pb.type

    if t != pb.STRUCT:
        print spaces + pb.name,":",
    else:
        print spaces + pb.name
        spaces += "  "

    if t == pb.DOUBLE:
        print str_list(pb.val_double)
    elif t == pb.FLOAT:
        print str_list(pb.val_float)
    elif t == pb.BOOL:
        print str_list(pb.val_bool)
    elif t == pb.STRING:
        print str_list(pb.val_string)
    elif t == pb.BYTES:
        print str_list(pb.val_bytes)
    elif t == pb.INT32:
        print str_list(pb.val_int32)
    elif t == pb.INT64:
        print str_list(pb.val_int64)
    elif t == pb.UINT32:
        print str_list(pb.val_uint32)
    elif t == pb.UINT64:
        print str_list(pb.val_uint64)
    elif t == pb.STRUCT:
        for s in pb.val_struct:
            print_parameter_value(s, spaces)


def get_parameter_value(pb):
    """Returns a single structure, or a list of structures, each structure
       analogous to a Parameter/Sampler DataDescriptor specified structure.

    """

    if len(pb.val_struct) > 1:
        d = {}
        d[str(pb.name)] = [_get_parameter_structure_value(p, {}) for p in pb.val_struct]
        return d
    else:
        return _get_parameter_structure_value(pb, {})

def _get_parameter_structure_value(pb, d):
    """Returns a dictionary of the parameter value, given a
    PBDataField. Since the PBDataField can recursively hold other
    PBDataFields, this function will recurse. Not meant for parameters
    that are top-level arrays. For those, iterate over the val_struct
    and pass each item to this.

    pb: The PBDataField to convert to dictionary

    d: Initial dictionary value

    """

    # All casts (str, etc.) & list comprehension done to prevent YAML
    # from defining protobuf and unicode stuff. Makes the output file
    # much more compact if using YAML to dump data to disk.
    t = pb.type

    if t == pb.STRUCT:
        md = {}

        for s in pb.val_struct:
             md[str(s.name)] = {}
             d[str(pb.name)] = _get_parameter_structure_value(s, md)

    elif t == pb.DOUBLE:
        d[str(pb.name)] = list(pb.val_double)
    elif t == pb.FLOAT:
        d[str(pb.name)] = list(pb.val_float)
    elif t == pb.BOOL:
        d[str(pb.name)] = list(pb.val_bool)
    elif t == pb.STRING:
        d[str(pb.name)] = [str(s) for s in pb.val_string]
    elif t == pb.BYTES:
        d[str(pb.name)] = list(pb.val_bytes)
    elif t == pb.INT32:
        d[str(pb.name)] = list(pb.val_int32)
    elif t == pb.INT64:
        d[str(pb.name)] = list(pb.val_int64)
    elif t == pb.UINT32:
        d[str(pb.name)] = list(pb.val_uint32)
    elif t == pb.UINT64:
        d[str(pb.name)] = list(pb.val_uint64)

    return d

def create_subscriber(ctx, sub_url, ds_pub_url, keys):
    """Given a context, a subscription URL, a directory service subscription
    URL, and the keys to subscribe to, creates a ZMQ subscriber socked.

    ctx: The ZMQ context object.

    sub_url: The device's PUB/SUB URL

    ds_pub_url: The directory service's PUB/SUB URL

    keys: The subscription keys.

    """
    subscriber = ctx.socket(zmq.SUB)
    subscriber.connect(sub_url)
    subscriber.connect(ds_pub_url)

    for key in keys:
        subscriber.setsockopt(zmq.SUBSCRIBE, key)

    return subscriber

def create_snapshot(ctx, snap_url):
    """Given a context and a snapshot URL, creates the REQ socket for the
    services snapshot service.

    ctx: The ZMQ context

    snap_url: The snapshot URL

    """
    snapshot = ctx.socket(zmq.REQ)
    snapshot.linger = 0
    snapshot.connect(snap_url)
    return snapshot

def get_every_parameter(ctx, major, minor):
    """Requests the key for every published parameter from the device
    'major.minor'. Returned as a list of strings.

    ctx: The 0MQ context

    major: The major device name (e.g. 'VEGAS')

    minor: The minor device name (e.g. 'BankAMgr')
    """
    req_url = get_directory_endpoints('request')
    url = get_service_endpoints(ctx, req_url, major, minor, 1)
    print req_url, major, minor, url
    request = ctx.socket(zmq.REQ)
    request.linger = 0

    request.connect(url)
    parts = ["LIST", major, minor]
    request.send_multipart(parts)

    buffers = request.recv_multipart()

    # get rid of 'END', and sort.
    buffers.pop()
    buffers.sort()
    return [p for p in buffers if ":P:" in p]

def get_snapshots(snap, keys):
    """Requests a snapshot for every key in keys, and returns a list of
    PBDataFields with the results in the same order that 'keys' is in.

    snap: The snapshot 0MQ socket

    keys: The list of keys

    """
    snap_pbs = []

    for i in keys:
        snap.send(i)
        rl = []
        rl = snap.recv_multipart()

        el = len(rl)

        if el == 1:  # Got an error
            if rl[0] == "E_NOKEY":
                pass
        elif el > 1:
            # first element is the key
            # the following elements are the values
            df = PBDataField()
            df.ParseFromString(rl[1])
            snap_pbs.append(df)

    return snap_pbs
