#!/bin/bash

./stop_spectrum_plots.sh

for d in a b c d e f g h
do
./spectrumplots.py ${d} -v warn &
done
