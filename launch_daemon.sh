#!/bin/bash -e
# Launch the daemon as root on the RaspberryPi
DIR=~/pcb_drill/pcb_drilld
source $DIR/../bin/activate
cd $DIR && sudo ./pcb_drilld.py
deactivate
