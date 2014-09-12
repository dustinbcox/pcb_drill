#!/bin/bash -e
# Launch the web interface
DIR=~/pcb_drill/pcb_drill_web
source $DIR/../bin/activate
cd $DIR && ./pcb_drill_web.py --debug
deactivate
