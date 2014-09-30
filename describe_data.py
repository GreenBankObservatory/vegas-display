#! /usr/bin/env python

import argparse

from DataStreamUtils import get_data_snapshot

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Obtain one sampler or parameter value and describe it')
    parser.add_argument('key', metavar='key', nargs=1,
                        help='The major device name.')
    args = parser.parse_args()
    key = args.key[0]

    print get_data_snapshot(key)
