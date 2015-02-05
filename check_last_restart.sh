#!/bin/bash

for d in 1 2 3 4 5 6 7 8 
do
ls -trd /home/gbt/etc/log/vegas-hpc${d}/vegasManager.* | tail -1
done
