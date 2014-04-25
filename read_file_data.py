import pyfits
import sys
from server_config import *

# define input files
def filenames(projid, scannum):
    project_directory = '/home/gbtdata/{proj}/'.format(proj=projid)
    scanlog_file = project_directory + 'ScanLog.fits'
    scanlog = pyfits.open(scanlog_file)
    project_files = scanlog['SCANLOG'].data[scanlog['SCANLOG'].data['SCAN']==scannum]['FILEPATH']
    LO_FILENAME = '/home/gbtdata/' + [x for x in project_files if 'LO1A' in x][0]
    IF_FILENAME = '/home/gbtdata/' + [x for x in project_files if 'IF' in x][0]
    return LO_FILENAME, IF_FILENAME

def lofreq(LO_FILENAME):
    lo =pyfits.open(LO_FILENAME)
    LO1FREQ = lo['LO1TBL'].data['LO1FREQ'][0]
    LO1 = LO1FREQ
    lo.close()
    return LO1

def ifinfo(IF_FILENAME):
    iffile = pyfits.open(IF_FILENAME)
    # add SFF_SIDEBAND, SFF_MULTIPLIER, SFF_OFFSET to if_table structure
    # using (BACKEND,PORT,BANK) as the key
    if_table = {}
    for x in iffile['IF'].data:
        key = (x['BACKEND'],x['PORT'],x['BANK'])
        if x['BACKEND'] == 'VEGAS':
            if_table[key] = (x['SFF_SIDEBAND'],
                             x['SFF_MULTIPLIER'],
                             x['SFF_OFFSET'])
    iffile.close()
    return if_table

def info_from_files(projid, scannum):
    lo_f, if_f = filenames(projid, scannum)
    lo1 = lofreq(lo_f)
    iftab = ifinfo(if_f)
    return lo1, iftab

def sky_freq(LO1, if_table, BACKEND_FILENAME):
    # sky frequency formula
    # sky = SFF_SIDEBAND*IF + SFF_MULTIPLIER*LO1 + SFF_OFFSET

    IF = backend_info(BACKEND_FILENAME)
    SFF_SIDEBAND,SFF_MULTIPLIER,SFF_OFFSET =  if_table[('VEGAS', 1, 'A')]

    sky = SFF_SIDEBAND*IF + SFF_MULTIPLIER*LO1 + SFF_OFFSET

    return sky

def backend_info(BACKEND_FILENAME):
    # IF(channel) = CRVAL1 + CDELT1 * (channel - CRPIX1)
    # these come from the backend fits file or **manager stream**
    vegas = pyfits.open(BACKEND_FILENAME)
    CRPIX1 = vegas['SAMPLER'].header['CRPIX1']
    CRVAL1 = vegas['SAMPLER'].data['CRVAL1'][0]
    CDELT1 = vegas['SAMPLER'].data['CDELT1'][0]

    print 'CRPIX1',CRPIX1
    print 'CRVAL1',CRVAL1
    print 'CDELT1',CDELT1

    nchan = vegas['PRIMARY'].header['NCHAN']
    IF = CRVAL1 + CDELT1 * (nchan/2 - CRPIX1)
    vegas.close()

    return IF

if __name__ == "__main__":
    """Usage: read_file_data.py AGBT13B_312_01 35"""

    project = sys.argv[1]
    scan = int(sys.argv[2])

    lo1, if_info = info_from_files(project, scan)
    BACKEND_FILENAME = '/lustre/gbtdata/{proj}/VEGAS/2014_03_11_09:31:34E.fits'.format(proj=project)
    
    sky = sky_freq(lo1, if_info, BACKEND_FILENAME)
    print '{0:.2f} GHz'.format((sky/1e9))
