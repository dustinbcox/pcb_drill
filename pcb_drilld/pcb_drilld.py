#!/home/pi/pcb_drill/bin/python

"""
pcb_drilld.py - main interface for launching a daemon to run selective commands as root user
"""

import argparse
import daemon
import lockfile
import signal
import subprocess
import grp
import time
import traceback
import os
import pwd
import logging
import zmq
import json
import sys
import math
import re
import SimpleCV
import ConfigParser
import picamera

# Insert Path for project ../ from here
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pcb_drill_common.pcb_drill_gcode import PcbDrillGCode

USE_RASPISTILL = False

def set_file_permissions(filename, mode=0644, user='pi', group='pi'):
    """ Set the permissions of a filename """
    os.chmod(filename, mode)
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    log.info("uid = " + str(uid) + " gid = " + str(gid))
    os.chown(filename, uid, gid)

class PcbDrillRPC(object):
    """ Execute a given command as an RPC server"""
    def __init__(self, image_storage, user, group):
        self._original_images = {}
        self._blobs = {}
        self._image_storage = image_storage
        self._user = user
        self._group = group
        self._drill_holes = {}
        self._solder_mask = {}
        self._camera = None
        self._camera_in_preview = False

    def _initialize_camera(self):
        if self._camera_in_preview:
            if self._camera is not None:
                self.stop_preview()
            else:
                log.error("_initialize_camera found _camera_in_preview without a _camera object")
        if self._camera is None:
            self._camera = picamera.PiCamera()
        self._camera.awb_mode = 'fluorescent'
        self._camera.contrast = 40
        self._camera.exif_tags['IFD0.Artist'] = "pcb_drilld"
        self._camera.exif_tags['IFD0.Copyright'] = "TODO"

    def _uninitialize_camera(self):
        if self._camera is not None:
            self._camera.close()
            self._camera = None
        

    def process_solder_mask(self, filename, session='default'):
        """ Process a solder mask that is a simple image which contains
            black "solder" blobs and find the center of those blobs"""
        rpc_data = {}
        image = self._load_image(filename)

        self._solder_mask[session] = self._build_filename(filename)

        image = image.binarize()

        blobs = image.findBlobs()
        self._blobs[filename] = blobs

        # Load same image
        image = SimpleCV.Image(self._solder_mask[session])

        dl = image.dl()

        count = blobs.count()
        holes = []
        for blob in blobs:
            (x, y) = blob.coordinates()
            holes.append((x,y))
            dl.circle(blob.coordinates(), 2, color=SimpleCV.Color.RED)
        image.addDrawingLayer(dl)
        image.applyLayers()
        solder_mask_image = self._build_filename("solder_mask" + filename)
        image.save(solder_mask_image)
        set_file_permissions(solder_mask_image, 0644, self._user, self._group)

        rpc_data['count'] = count
        rpc_data['cv_solder_mask_filename'] = solder_mask_image
        rpc_data['holes'] = "\n".join(["({0},{1})".format(*hole) for hole in holes])

        self._drill_holes[filename] = holes
        rpc_data.update(self.generate_gcode(filename))
        return rpc_data

    def capture_image(self, filename, width=800, height=600):
        """ Capture an image using platform specific tools (e.g. raspberry pi uses raspistill)
            requires filename:
        """
        width = int(width)
        height = int(height)
        full_path = self._build_filename(filename)
        if USE_RASPISTILL: 
            subprocess.check_call(['/usr/bin/raspistill', '-h', str(height),
                                   '-w', str(width), '-o', full_path, '-t', '5'])
        else:
            self._initialize_camera()
            self._camera.resolution = (width, height)
            self._camera.capture(full_path)
            
        set_file_permissions(full_path, 0644, self._user, self._group)

        return full_path

    def calibrate_pcb(self, pcb_filename, session='default'):
        """ Calibrate the PCB on the bed """
        rpc_data = {}
        pcb_fullpath = self._build_filename(pcb_filename)
        pcb_image = SimpleCV.Image(pcb_fullpath)
        pcb_image_bin = pcb_image.binarize()
        if session not in self._solder_mask:
            raise ValueError("You must process a solder mask image 1st")
        solder_mask = SimpleCV.Image(self._solder_mask[session])#.binarize().invert()
        keypoint = pcb_image_bin.findKeypointMatch(solder_mask)
        if keypoint is None:
            raise ValueError("Unable to locate board based on solder mask")

        pcb_only = keypoint[0].crop()

        pcb_only_filename = "crop_pcb_" + pcb_filename
        pcb_only.save(self._build_filename(pcb_only_filename))
        set_file_permissions(self._build_filename(pcb_only_filename), 0644, self._user, self._group)
        rpc_data['pcb_cropped_filename'] = pcb_only_filename

        delta_x = keypoint[0].topRightCorner()[0] - keypoint[0].topLeftCorner()[0]
        delta_y = keypoint[0].bottomRightCorner()[1] - keypoint[0].topRightCorner()[1]
        angle = math.atan2(delta_y, delta_x)

        solder_mask_bin = solder_mask.binarize()
        solder_mask_bin_image_mask = solder_mask_bin.rotate(angle).scale(keypoint[0].width(), keypoint[0].height())
        blobs = pcb_only.findBlobsFromMask(solder_mask_bin_image_mask)
        rpc_data['count'] = blobs.count()

        rpc_data['angle'] = angle
        log.info("keypoint x = {0}, y = {1}".format(keypoint.x(), keypoint.y()))

        cv_filename = "cv_" + pcb_filename
        pcb_image.draw(keypoint, SimpleCV.Color.FUCHSIA, width=2)

        for blob in blobs:
            point = keypoint[0].topLeftCorner() + blob.coordinates()
            pcb_image.drawCircle(point, 4, color=SimpleCV.Color.RED)


        pcb_image.save(self._build_filename(cv_filename))

        cv_keypoint_image = pcb_image_bin.drawKeypointMatches(solder_mask)
        cv_keypoint_filename = "cv_keypoint_" + pcb_filename
        cv_keypoint_image.save(self._build_filename(cv_keypoint_filename))
        set_file_permissions(self._build_filename(cv_keypoint_filename), 0644, self._user, self._group)
        rpc_data['cv_keypoint_filename'] = cv_keypoint_filename

        set_file_permissions(self._build_filename(cv_filename), 0644, self._user, self._group)
        rpc_data['cv_image'] = cv_filename 

        return rpc_data


    def calibrate_printer(self, pre_drill_filename, post_drill_filename):
        """ Calibrate size according to the gcode that drills three holes """
        pre_drill_filename = self._build_filename(pre_drill_filename)
        post_drill_filename = self._build_filename(post_drill_filename)
        pre_drill_image = SimpleCV.Image(pre_drill_filename)
        post_drill_image = SimpleCV.Image(post_drill_filename)
        diff_image = post_drill_image - pre_drill_image
        pre_drill_image = None
        post_drill_image = None
        rpc_data = {}
        diff_image = diff_image.binarize()
        blobs = diff_image.findBlobs()
        log.debug("calibrate printer")
        for i, blob in enumerate(blobs):
            blob_center = blob.coordinates()
            log.debug("{0} blob - ({1},{2})".format(i, blob_center[0], blob_center[1]))
        if len(blobs) != 3:
            #raise ValueError("Unable to calibrate image since it has {0} differences between images".format(len(blobs)))
            rpc_data['warning'] = "Unable to calibrate image since it has {0} differences between images".format(len(blobs))
        diff_image_filename = "diff_" + os.path.basename(post_drill_filename)
        diff_image.save(self._build_filename(diff_image_filename))
        set_file_permissions(self._build_filename(diff_image_filename), 0644, self._user, self._group)
        rpc_data['cv_image_filename'] = diff_image_filename
        rpc_data['cv_image_fullname'] = self._build_filename(diff_image_filename)
        rpc_data['count'] = len(blobs)

        return rpc_data
        #calibrate_image = time.strftime("calibrate_%Y_%m_%d_%H_%M_%S.jpg")
        #calibrate_image = self.capture_image(calibrate_image, 1024, 768)

    def start_preview(self):
        """ Start the RaspberryPi Camera """
        self._initialize_camera()
        if not self._camera_in_preview:
            log.info("Starting preview")
            self._camera_in_preview = True
            self._camera.start_preview()

    def stop_preview(self):
        if self._camera is not None and self._camera_in_preview:
            log.info("Stop preview")
            self._camera.stop_preview()
            self._camera_in_preview = False
            self._camera.close()
            self._camera = None

    def generate_gcode(self, filename, prefix=None, postfix=None):
        generator = PcbDrillGCode(prefix, postfix, line_numbers=False)
        generator.comment("Generated from pcb_drilld daemon at " + time.ctime())
        holes = self._drill_holes[filename]
        generator.drill_holes(holes)
        generator.comment("Processed {0} drill holes".format(len(holes)))
        prefix = generator.prefix
        postfix = generator.postfix
        gcode = generator.generate()
        body = generator.body
        return {'prefix': prefix, 'postfix': postfix, 'body': body, 'gcode': gcode}

    def _build_filename(self, base_filename):
        """ build the full pathname and ensure the name is safe"""
        if re.match(r'^[0-9A-Za-z\._-]+$', base_filename) is None:
            raise ValueError("Filename has characters outside of A-Za-z-_.")
        # Don't use os.path.join as it will follow ../
        if not base_filename.lower().endswith(".png") and \
           not base_filename.lower().endswith(".jpg"):
            base_filename += ".png"
        full_path = self._image_storage + os.path.sep + base_filename
        return full_path

    def _load_image(self, filename):
        # TODO handle filename security
        full_filename = self._build_filename(filename)
        return SimpleCV.Image(full_filename)

    #def _binarize_image(self, session, threshold=-1):
    #    """ Binarize an image file"""
    #    return self._original_images[session].binarize(threshold)

    def _crop_image(self, session, x, y, w, h):
        return self._original_images[session].crop(x, y, w, h)
    def _rotate_image(self, session, degrees):
        return self._original_images[session].rotate(degrees)

       
class PcbDrillServer(object):
    """ Run the actual server """
    def __init__(self, rpc):
        log.info("Starting PcbDrillServer...")
        self._methods = self._get_rpc_methods(rpc)
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REP)

    def _request(self):
        request = json.loads(self._socket.recv())
        ascii_request = {}
        for k,v in request.items():
            if hasattr(k, 'encode') and hasattr(v, 'encode'):
                ascii_request[k.encode("utf8")] = v.encode("utf8")
            else:
                # Handles ints and other things
                ascii_request[k] = v
        return ascii_request

    def _response(self, data):
        self._socket.send(json.dumps(data))

    def _execute(self, request):
        command = request['command']
        del request['command']
        kwargs = request
        log.info("Command: " + str(command) + " Arguments: " + str(kwargs))
        start_time = time.time()
        response = self._methods[command](**kwargs)
        end_time = time.time()
        duration = end_time - start_time

        return {'success': True, 'output': response, 'time': duration}
            
    def _get_rpc_methods(self, rpc):
        methods = {}
        log.info("rpc = " + str(rpc))
        for method in dir(rpc):
            if not method.startswith("_") and \
                callable(getattr(rpc, method)):
                methods[method] = getattr(rpc, method)
        log.info("Currently supporing the following methods:" \
                 + " ".join(sorted(methods.keys())))
        return methods

    def bind(self, address):
        """ ZeroMQ Binding """
        self._socket.bind(address)

    def run(self):
        while True:
            response = {'error': 'premature exit'}
            try:
                request = self._request()
                response = self._execute(request)
                # Fall through to finally
            except Exception as error:
                exception_output = traceback.format_exception(*sys.exc_info())
                response = {'success': False, 'error': str(error),
                            'exception': "!! ".join(exception_output)}
                log.exception(error)
            finally:
                self._response(response)

log = None

def main(config_file, log_level):
    """ Run the daemon """
    #logging.basicConfig(filename='/tmp/pcb_drilld.log', level=log_level)
    global log
    config_parser = ConfigParser.ConfigParser()
    config_parser.read(config_file)
    
    log = logging.getLogger('pcb_drilld')
    log.setLevel(log_level)
    handler = logging.FileHandler(config_parser.get('daemon', 'logfile'))
    log.addHandler(handler)

   #pid = #daemon.pidlockfile.TimeoutPIDLockFile('/var/run/pcb_drilld.pid', 10)
    pid = lockfile.FileLock('/var/run/pcb_drilld.pid')
    daemon_context = daemon.DaemonContext(working_directory='/tmp', pidfile=pid,
                                          files_preserve=[handler.stream])
    daemon_context.signal_map = {
        signal.SIGTERM: 'terminate',
    }

    log.info("Attemping to run as a daemon")

    # Change permissions of the logging file (after our 1st message)
    set_file_permissions(config_parser.get('daemon', 'logfile'), 0644,
                         config_parser.get('daemon', 'user'),
                         config_parser.get('daemon', 'group'))

    with daemon_context:
        try:
            log.info("Started pcb_drilld as a daemon: PID=%d" % os.getpid())
            server = PcbDrillServer(PcbDrillRPC(config_parser.get('daemon', 'image_storage'),
                                                config_parser.get('daemon', 'user'),
                                                config_parser.get('daemon', 'group')))
            server.bind(config_parser.get('daemon', 'zeromq_socket'))
            server.run()
        except Exception as error:
            log.error("Problem while trying to become a daemon")
            log.exception(error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "PCB Drill Daemon")
    parser.add_argument('--debug',action='store_true', help="Enables debug mode")
    parser.add_argument('--config', help="Specify configuration file",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "../pcb_drill.ini"))

    args = parser.parse_args()

    if args.debug is True:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    main(args.config, log_level)
