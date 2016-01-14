#!/bin/bash

fullpath=`readlink -f $0`
pathdir=`dirname $fullpath`

${pathdir}/stop_spectrum_plots.sh

for d in a b c d e f g h
do
${pathdir}/spectrumplots.py ${d} -v warn &
done
