#!/bin/bash

# define a function to check the existence of a file
#  and source it if it exists
source_file()
{
    if test -e $1; then
	source $1
    else
	echo "Can not find $1. Exiting."
	exit 1
    fi
}

source_file /home/gbt/gbt.bash
source_file /home/gbt7/newt/McPython.bash
source_file /home/gbt7/vegas_display/bin/activate

fullpath=`readlink -f $0`
pathdir=`dirname $fullpath`

${pathdir}/stop_waterfall_plots.sh

for d in a b c d e f g h
do
    # xvfb-run ${pathdir}/../waterfall.py ${d} -v warn &
    GDFONTPATH=/usr/share/fonts/liberation GNUPLOT_DEFAULT_GDFONT=LiberationSans-Regular ${pathdir}/../waterfall.py ${d} -v warn &
done
