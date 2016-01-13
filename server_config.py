"""
Global options for creating plots and running display server.
"""

import logging

ALWAYS_UPDATE = False

# waterfall plot dimensions
NROWS = 100
NCHANS = 512  # number of channels for client to display

UPDATE_RATE = 10  # seconds

# configure the logger
log_level = {"err":   logging.ERROR,
             "warn":  logging.WARNING,
             "info":  logging.INFO,
             "debug": logging.DEBUG}
