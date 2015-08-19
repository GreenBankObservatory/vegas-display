#!/bin/bash

source /home/gbt/gbt.bash
source /home/gbt7/newt/McPython.bash
source /home/gbt7/vegas_display/bin/activate

fullpath=`readlink -f $0`
pathdir=`dirname $fullpath`

${pathdir}/start_spectrum_plots.sh
${pathdir}/start_waterfall_plots.sh
