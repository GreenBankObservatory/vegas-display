#!/bin/bash

./stop_waterfall_plots.sh

for d in a b c d e f g h
do
./waterfall.py ${d} -v warn &
done
