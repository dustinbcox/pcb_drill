#!/bin/bash
sudo kill `ps aux | grep pcb_drilld  | grep "^root" | awk '{print $2}'`
