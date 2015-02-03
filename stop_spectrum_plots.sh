#!/bin/bash

fullpath=`readlink -f $0`
pathdir=`dirname $fullpath`

pkill -f "${pathdir}/spectrumplots.py"
