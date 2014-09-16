import pdb
from pprint import pprint
from random import randint
import numpy as np

LIVE = True
DEBUG = True
UPDATES_DEBUG = True
DO_PARSE = True

PORT_NUMBER = 7777

BANK_NUM = {'A':0, 'B':1, 'C':2, 'D':3,
            'E':4, 'F':5, 'G':6, 'H':7}

NCHANS = 512  # number of channels for client to display


class DF:
    project_id = 'ProjectFOO'
    scan_number = randint(0, 9999)
    integration = randint(0, 9999)
    time = 100
    cal_state = None
    sig_ref_state = None
    data_dims = 1024
    data = np.random.random(1024)

