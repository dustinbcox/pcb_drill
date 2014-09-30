pcb_drill
=========

## Intro

This project uses a Raspberry Pi and a modified 3D printer (Prusa I3) with a mounted drill to become an automated
pcb drilling machine. It uses Python and SimpleCV and is licensed under the GPL3.

The web interface converts a solder mask and following a calibration sequence you can product gcode to feed into say Octoprint.

*under active development*

## Installation Instructions

*These are my notes*

* Download and install Raspbian Wheezy (2014-01-07) onto an SD card
  - OS X
    - Ensure that you locate the disk:
    - diskutil list
    - sudo dd if=2014-01-07-wheezy-raspbian.img of=/dev/rdisk1 bs=4m
  - Linux
    - dmesg | grep sd
    - sudo dd if=2014-01-07-wheezy-raspbian.img of=/dev/sdb bs=4M # provided sdb is the sd card
* Upon first boot configure the following (raspi-config will autostart):
  - expand filesystem
  - change your password
  - consider overclocking to TURBO (however, if you experience any stability problems back down to medium)
  - Internationalisation Options
    - change timezone
    - change keyboard layout
  - Reboot
* Configure networking (use nano or vim or whatever)
  - sudo nano /etc/wpa\_suplicant/wpa_suplicant.conf
  - sudo service networking restart
* Firmware Updates
  - sudo rpi-update
  - reboot
* Software Updates
  - sudo apt-get update
  - sudo apt-get upgrade
  - reboot if you want
* Configure the /boot/config.txt file and add these parameters:
  - This is because pygame fails to draw lines (used by SimpleCV). See http://www.raspberrypi.org/forums/viewtopic.php?p=89931#p89931.
    - framebuffer_depth=32
    - framebuffer\_ignore_alpha=1 
  - Disable the camera LED as it causes unnecessary reflection
    - disable\_camera_led=1
* Install Python 2.7 & PIP (package installer for Python)
  - sudo apt-get install python-pip
* Install virtualenv
  - sudo apt-get install python-virtualenv
* Install Octoprint from source
  - Follow these instructions: https://github.com/foosel/OctoPrint/wiki/Setup-on-a-Raspberry-Pi-running-Raspbian
* Install SimpleCV (instructions from: http://simplecv.readthedocs.org/en/latest/HOWTO-Install%20on%20RaspberryPi.html?highlight=opencv)
  - sudo apt-get install python-opencv python-scipy python-numpy python-setuptools
  - sudo pip install https://github.com/sightmachine/SimpleCV/zipball/master
  - sudo pip install svgwrite
* Install pcb_drill (me!!)
  - Download the code from github
    - cd ~
    - git clone git@github.com:dustinbcox/pcb_drill.git
  - or (if you have network restructions and can only use http/https)
    - git clone https://github.com/dustinbcox/pcb_drill.git
* Setup the virtualenv (or quasivirtualenv since SimpleCV didn't play nicely)
  - Since we install system python libraries we need to create a virtualenv that supports that:
    - virtualenv --system-site-packages pcb_drill
    - cd pcb_drill
    - source bin/activate
    - pip install -r requirements.txt
* Run nginx_config/setup.sh to configure nginx with SSL


