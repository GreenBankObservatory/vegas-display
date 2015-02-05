#!/bin/bash

fullpath=`readlink -f $0`
pathdir=`dirname $fullpath`

${pathdir}/start_spectrum_plots.sh
${pathdir}/start_waterfall_plots.sh
