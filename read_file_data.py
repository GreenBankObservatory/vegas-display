try:
    from astropy.io import fits as pyfits
except ImportError:
    import pyfits

import sys
import logging


# define input files
def filenames(projid, scannum):
    project_directory = '/home/gbtdata/{proj}/'.format(proj=projid)
    scanlog_file = project_directory + 'ScanLog.fits'
    scanlog = pyfits.open(scanlog_file)
    project_files = scanlog['SCANLOG'].data[scanlog['SCANLOG'].data['SCAN'] == scannum]['FILEPATH']
    lo_filename = '/home/gbtdata/' + [x for x in project_files if 'LO1A' in x][0]
    if_filename = '/home/gbtdata/' + [x for x in project_files if 'IF' in x][0]
    return lo_filename, if_filename


def lofreq(lo_filename):
    lo = pyfits.open(lo_filename)
    local_oscillator_freq = lo['LO1TBL'].data['LO1FREQ'][0]

    # Get the frequency offset information for frequency-switched integrations.
    offset = 0
    for x in lo['STATE'].data:
        if x['SIGREF'] == 1:
            offset = x['FREQOFF']
            break

    lo.close()
    return local_oscillator_freq, offset


def ifinfo(if_filename):
    iffile = pyfits.open(if_filename)

    # add SFF_SIDEBAND, SFF_MULTIPLIER, SFF_OFFSET to if_table structure
    # using (PORT,BANK) as the key
    if_table = {}
    for x in iffile['IF'].data:

        key = (x['PORT'], x['BANK'])

        if x['BACKEND'] == 'VEGAS':
            if_table[key] = (x['POLARIZE'], x['SFF_SIDEBAND'], x['SFF_MULTIPLIER'], x['SFF_OFFSET'])

    iffile.close()
    return if_table


def info_from_files(projid, scannum):
    lo_f, if_f = filenames(projid, scannum)
    lcllo1, offset = lofreq(lo_f)
    iftab = ifinfo(if_f)
    return lcllo1, offset, iftab


def backend_info(backend_fname):
    # IF(channel) = crval1 + cdelt1 * (channel - crpix1)
    # these come from the backend fits file or **manager stream**
    vegas = pyfits.open(backend_fname)
    crpix1 = vegas['SAMPLER'].header['crpix1']
    crval1 = vegas['SAMPLER'].data['crval1'][0]
    cdelt1 = vegas['SAMPLER'].data['cdelt1'][0]

    logging.debug('crpix1 {}'.format(crpix1))
    logging.debug('crval1 {}'.format(crval1))
    logging.debug('cdelt1 {}'.format(cdelt1))

    nchan = vegas['PRIMARY'].header['NCHAN']
    intermediate_frequency = crval1 + cdelt1 * (nchan/2 - crpix1)
    vegas.close()

    return intermediate_frequency


if __name__ == "__main__":
    """Usage: read_file_data.py AGBT13B_312_01 35"""

    project = sys.argv[1]
    scan = int(sys.argv[2])

    lo1, if_info = info_from_files(project, scan)
    backend_filename = '/lustre/gbtdata/{proj}/VEGAS/2014_03_11_09:31:34E.fits'.format(proj=project)

