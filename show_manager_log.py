#! /usr/bin/env python

import zmq
import argparse
from DataStreamUtils import get_service_endpoints, get_directory_endpoints
from request_pb2 import *

def get_tcp_url(urls):
    for u in urls:
        if "tcp" in u:
            return u
    return ""

def create_subscriber(ctx, sub_url, ds_pub_url, keys):
    subscriber = ctx.socket(zmq.SUB)
    subscriber.connect(sub_url)
    subscriber.connect(ds_pub_url)

    for key in keys:
        subscriber.setsockopt(zmq.SUBSCRIBE, key)

    return subscriber

def main():
    """Subcribes to a manager's log stream, and prints the log stream to
    stdout. Call with major (and optionally minor) device name on
    command line to follow that manager's log stream.

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
    sub_urls = get_service_endpoints(context, req_url, major, minor, 0)

    # subscription keys. We're interested in the 'cout' and 'cerr'
    # streams from the manager, and the NEW_INTERFACE message from the
    # directory service:
    keys = ["%s.%s:cout" % (major, minor),
            "%s.%s:cerr" % (major, minor),
            "YgorDirectory:NEW_INTERFACE"]

    sub_url = get_tcp_url(sub_urls)

    if not sub_url:
        print "Directory reports no device %s.%s. Exiting..." % (major, minor)
    else:
        subscriber = create_subscriber(context,
                                       get_tcp_url(sub_urls),
                                       dir_pub_url, keys)
        try:
            while True:
                # Read envelope with address
                [key, payload] = subscriber.recv_multipart()

                if key == keys[0]:
                    print payload
                elif key == keys[1]:
                    print "ERROR:", payload
                elif key == keys[2]:
                    # directory service, new interface. If it's ours,
                    # need to reconnect.
                    reqb = PBRequestService()
                    reqb.ParseFromString(payload)

                    # If we're here it's because our device restarted,
                    # or name server came back up. If the manager
                    # restarted the URL will be different, and we need
                    # to resubscribe. Check for the publishing interface
                    # (0). If not, we might respond to a message for the
                    # wrong interface, in which case 'publish_url' will
                    # be empty and the connection attempt below will
                    # fail.
                    if reqb.major == major and reqb.minor == minor and reqb.interface == 0:
                        new_url = get_tcp_url(reqb.publish_url)

                        if sub_url != new_url:
                            print "Manager restarted: ", reqb.host, reqb.major, reqb.minor, reqb.interface, new_url
                            sub_url = new_url

                            if sub_url:
                                subscriber.close()
                                subscriber = create_subscriber(context,
                                                               sub_url,
                                                               dir_pub_url, keys)
                            else:
                                print "Manager %s.%s subscription URL is empty! exiting..." % (major, minor)
                                return
        except KeyboardInterrupt, e:
            subscriber.close()
            context.term()

if __name__ == "__main__":
    main()
