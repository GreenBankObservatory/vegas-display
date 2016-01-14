#!/bin/bash

fullpath=`readlink -f $0`
pathdir=`dirname $fullpath`

${pathdir}/stop_spectrum_plots.sh
${pathdir}/stop_waterfall_plots.sh
