#!/bin/bash

fullpath=`readlink -f $0`
pathdir=`dirname $fullpath`

${pathdir}/stop_waterfall_plots.sh

for d in a b c d e f g h
do
${pathdir}/waterfall.py ${d} -v warn &
done
