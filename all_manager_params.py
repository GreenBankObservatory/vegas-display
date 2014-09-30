#! /usr/bin/env python

import zmq
import yaml
import argparse
import os
from DataStreamUtils import *
from request_pb2 import *
from PBDataDescriptor_pb2 import *
from datetime import datetime
from gbt.ygor import getConfigValue


def get_data_file(major, minor):
    """Returns a filename, where the components are:

       <major>.<minor>.<date>.yaml

       The date will change at midnight, so one file per day.

    """
    my_path = getConfigValue('.', 'YGOR_LOGS')
    my_path += '/' + major + '-' + minor + '-stream/manager-state/'

    try:
        os.stat(my_path)
    except OSError as e:
        if e[0] == 2: # No such file or directory
            os.mkdir(my_path)

    return my_path + datetime.now().date().isoformat() + ".yaml"

def main():
    """Subcribes to a manager's 'state' parameter, and prints the value of
    every manager parameter to stdout when that state transitions to
    'Ready' or to 'Running'. Call with major (and optionally minor)
    device name on command line to follow that manager's state.

    """

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

    # Set up 0MQ and get the manager's publisher URLs
    context = zmq.Context(1)
    req_url = get_directory_endpoints('request')
    dir_pub_url = get_directory_endpoints('publisher')
    sub_url = get_service_endpoints(context, req_url, major, minor, 0)
    snap_url = get_service_endpoints(context, req_url, major, minor, 1)

    # subscription keys. We're interested in every parameter that the
    # manager has, + the YgorDirectory:NEW_INTERFACE sot that we can
    # continue if the manager is restarted.
    keys = ["%s.%s:P:state" % (major, minor), "YgorDirectory:NEW_INTERFACE"]
    pkeys = [p for p in get_every_parameter(context, major, minor)]

    if not sub_url:
        print "Directory reports no device %s.%s. Exiting..." % (major, minor)
    else:
        subscriber = create_subscriber(context,
                                       sub_url,
                                       dir_pub_url, keys)
        snapshot = create_snapshot(context, snap_url)

        try:
            while True:
                # Read envelope with address
                [key, payload] = subscriber.recv_multipart()

                if key == keys[-1]:
                    # directory service, new interface. If it's ours,
                    # need to reconnect.
                    reqb = PBRequestService()
                    reqb.ParseFromString(payload)

                    # If we're here it's possibly because our device
                    # restarted, or name server came back up, or some
                    # other service registered with the directory
                    # service. If the manager restarted the 'major',
                    # 'minor' and 'interface' will mach ours, and the
                    # URL will be different, so we need to
                    # resubscribe. Check for the publishing interface
                    # (0). If not, we might respond to a message for the
                    # wrong interface, in which case 'publish_url' will
                    # be empty and the connection attempt below will
                    # fail.

                    print reqb.major, reqb.minor, reqb.url

                    if reqb.major == major and reqb.minor == minor and reqb.interface == 0:
                        new_url = reqb.url[0]

                        if sub_url != new_url:
                            restart_msg = "Manager restarted: %s.%s, %s, %s" % \
                                          (reqb.major, reqb.minor, reqb.interface, new_url)
                            print restart_msg
                            data_file = get_data_file(major, minor)
                            msg = {}
                            msg[datetime.now()] = {'MSG': restart_msg}

                            with open(data_file, 'a') as outfile:
                                outfile.write(yaml.dump(msg, default_flow_style = None))

                            sub_url = new_url

                            if sub_url:
                                subscriber.close()
                                subscriber = create_subscriber(context,
                                                               sub_url,
                                                               dir_pub_url, keys)

                            # get new snap url as well.
                            snap_url = get_service_endpoints(context, req_url, major, minor, 1)

                            if snap_url:
                                print "new snap_url:", snap_url
                                snapshot.close()
                                snapshot = create_snapshot(context, snap_url)
                            else:
                                print "Manager %s.%s subscription URL is empty! exiting..." % (major, minor)
                                return

                elif ':P:state' in key:
                    state_data = {}
                    dt = datetime.now()
                    pb = PBDataField()
                    pb.ParseFromString(payload)
                    state_data[dt] = {}
                    if pb.val_struct[0].val_string[0] == 'Ready' \
                       or pb.val_struct[0].val_string[0] == 'Running' \
                       or pb.val_struct[0].val_string[0] == 'Aborting':
                        snaps = get_snapshots(snapshot, pkeys)

                        for s in snaps:
                            state_data[dt][str(s.name)] = get_parameter_value(s, {})
                    else:
                        state_data[dt][str(pb.name)] = get_parameter_value(pb, {})

                    data_file = get_data_file(major, minor)
                    with open(data_file, 'a') as outfile:
                        # 'default_flow_style = None' gives best
                        # compromise between human readable and space
                        # used. Here diff is 'None' ~3% larger than 'True'
                        outfile.write(yaml.dump(state_data, default_flow_style = None))
                else:
                    print "Unrecognized key:", key

        except KeyboardInterrupt, e:
            subscriber.close()
            snapshot.close()
            context.term()

if __name__ == "__main__":
    main()
