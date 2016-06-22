#!/bin/bash

# define the display number from a command line argument
export DISPLAY=:$1

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

${pathdir}/stop_spectrum_plots.sh

for d in a b c d e f g h
do
${pathdir}/../spectrumplots.py ${d} -v warn &
done
