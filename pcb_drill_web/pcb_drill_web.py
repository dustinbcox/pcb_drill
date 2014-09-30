#!/home/pi/pcb_drill/bin/python

import argparse
import json
import os
import random
import sys
import time
import datetime
import ConfigParser
import StringIO

from flask import Flask, render_template, request, url_for, g, make_response, abort, session, redirect, flash
from werkzeug.utils import secure_filename
from werkzeug.local import LocalProxy

app = Flask(__name__)

#LIBRARY_PATH = os.path.expanduser("~/pcb_drill_library")
GCODE_LIBRARY = ""
IMAGE_STORAGE = ""
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 768

# Insert Path for project ../ from here
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pcb_drill_common.pcb_drill_client import PcbDrillClient
from pcb_drill_common.pcb_drill_gcode import calibrate_printer, eject_bed, retract_bed

from navigation_menu import NavigationMenuItem, NavigationMenu


def get_nav_menu_items():
    """ Create the literal Nav Menu"""
    nav_menu = NavigationMenu(name='index')
    nav_menu.add(NavigationMenuItem('Home', 'index'))
    
    calibration = NavigationMenu('Calibrate', 'index')
    calibration.add(NavigationMenuItem('Camera', 'calibrate_camera'))
    calibration.add(NavigationMenuItem('Printer', 'calibrate_printer'))
    calibration.add(NavigationMenuItem('PCB', 'calibrate_pcb'))
    nav_menu.add(calibration)

    main_menu = NavigationMenu('Main', 'main', action='')
    main_menu.add(NavigationMenuItem('Solder Mask', 'main', action='soldermask'))
    main_menu.add(NavigationMenuItem('GCode', 'main', action='gcode'))
    main_menu.add(NavigationMenuItem('Library', 'library', filename=''))

    nav_menu.add(main_menu)

    nav_menu.add(NavigationMenuItem('Octoprint', 'octoprint'))
    
    nav_menu.add(NavigationMenuItem('About...', 'about'))

    nav_menu_items = getattr(g, '_nav_menu_items', None)
    if nav_menu_items is None:
        nav_menu_items = g._nav_menu_items = nav_menu
    return nav_menu_items


class DaemonError(Exception):
    def __init__(self, response):
        self.value = response
    def __str__(self):
        return repr(self.value)


def generate_response(name, template, **kwargs):
    """ Handle the general response with template rendering, etc"""
    nav_menu_bar = LocalProxy(get_nav_menu_items)
    nav_menu_bar.set_active(name)
    body = render_template(template, current_date=time.ctime(), **kwargs)
    response = make_response(body)
    # ;-)
    response.headers['X-Powered-By'] = 'Not-PHP/1.0'
    if 'pcb_drill_session' not in session:
        session['pcb_drill_session'] = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S.%f')
    return response

def connect_to_daemon():
    """Connect to background daemon """
    daemon = getattr(g, 'daemon', None)
    if daemon is None:
        daemon = g.daemon = PcbDrillClient()
        daemon.connect("tcp://localhost:5555")
    return daemon

def send_command(*args, **kwargs):
    """ send RPC command to daemon from Flask"""
    daemon = LocalProxy(connect_to_daemon)
    response = daemon(*args, **kwargs)
    if 'exception' in response:
        raise DaemonError(response)
    return response
    

def internal_error(message=None):
    if message is not None:
        flash("Last Error:" + str(message))
    return redirect(url_for('index')), 500

@app.route('/')
def index():
    return generate_response("index", "index.html")


@app.route('/calibrate/printer', methods=['GET', 'POST'])
def calibrate_printer():
    pre_image_filename = session.get('pre_image_filename', None)
    post_image_filename = session.get('post_image_filename', None)
    cv_image_filename = None

    try:
        if request.method == "POST":
            pre_image_method = request.form.get("pre_image_method")
            post_image_method = request.form.get("post_image_method")
            if 'pcb_drill_session' not in session:
                return internal_error("Invalid session, redirecting to index")

            if pre_image_method is not None:
                print "pre_image_method: ", pre_image_method
                if pre_image_method == "camera":
                    filename = session['pcb_drill_session'] + "-printer_pre_image.png"
                    message = send_command('capture_image', filename=filename, width="1024", height="768")
                    flash("pcb_drilld" + message['output'] + " duration=" + str(message['time']) + " second(s)")
                    pre_image_filename = url_for('static', filename="pcb_drill_image_library/" + filename)
                    session['pre_image_filename'] = pre_image_filename
            if post_image_method is not None:
                print "post_image_method: ", post_image_method
                if post_image_method == "camera":
                    filename = session['pcb_drill_session'] + "-printer_post_image.png"
                    message = send_command('capture_image', filename=filename, width="1024", height="768")
                    flash("pcb_drilld" + message['output'] + " duration=" + str(message['time']) + " second(s)")
                    post_image_filename = url_for('static', filename="pcb_drill_image_library/" + filename)
                    session['post_image_filename'] = post_image_filename
            if 'pre_image_filename' in session and session['pre_image_filename'] is not None and \
                'post_image_filename' in session and session['post_image_filename'] is not None:
                print "Attempt printer calibration"
                del session['pre_image_filename']
                del session['post_image_filename']
                message = send_command('calibrate_printer', pre_drill_filename=os.path.basename(pre_image_filename), post_drill_filename=os.path.basename(post_image_filename))
                cv_image_filename = url_for('static', filename="pcb_drill_image_library/" + message['output']['cv_image_filename'])
    except DaemonError as error:
        return internal_error(error)

    return generate_response('calibrate_printer','calibrate/printer.html', pre_image_filename=pre_image_filename,
                             post_image_filename=post_image_filename, cv_image_filename=cv_image_filename)

@app.route('/calibrate/pcb', methods=['GET', 'POST'])
def calibrate_pcb():
    if request.method == "GET":
        return generate_response('calibrate_pcb', 'calibrate/pcb.html')

    elif request.method == "POST":
        if 'pcb_drill_session' not in session:
            return internal_error("Invalid session, redirecting to index")
        capture = request.form.get("capture")
        try:
            if capture:
                filename = session['pcb_drill_session'] + "-calibrate_pcb.png"
                message = send_command('capture_image', filename=filename, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT)
                flash("pcb_drilld" + message['output'] + " duration=" + str(message['time']) + " second(s)")
                session['calibrate_pcb_filename'] = filename
            else:
                if 'pcb_image' in request.files:
                    f = request.files['pcb_image']
                    filename = session['pcb_drill_session'] + "calibrate_pcb_upload_" + secure_filename(f.filename) 
                    filepath = IMAGE_STORAGE + "/" + filename
                    f.save(filepath)
                else:
                    return internal_error("No file actually uploaded")

            calibrate_pcb_fullpath = url_for('static', filename=os.path.basename(IMAGE_STORAGE)+ "/" + filename)
            message = send_command('calibrate_pcb', pcb_filename=filename)
            flash("pcb_drilld" + str(message['output']) + " duration="  + str(message['time']) + " second(s)")
            return generate_response('calibrate_pcb', 'calibrate/pcb.html', calibrate_pcb_fullpath=calibrate_pcb_fullpath,
                                        cv_keypoint_fullpath = url_for('static', filename="pcb_drill_image_library/" + message['output']['cv_keypoint_filename']),
                                        #pcb_cropped_fullpath = url_for('static', filename="pcb_drill_image_library/" + message['output']['pcb_cropped_filename']),
                                        cv_image_fullpath = url_for('static', filename="pcb_drill_image_library/" + message['output']['cv_image']))

        except DaemonError as error:
            return internal_error(error)

@app.route('/calibrate/camera', methods=['GET', 'POST'])
def calibrate_camera():
    if request.method == "POST":
        try:
            preview_on = request.form.get('preview_on')
            if preview_on == "1":
                send_command('start_preview')
            elif preview_on == "0":
                send_command('stop_preview')
            else:
                return internal_error("Invalid command for preview_on")
        except DaemonError as error:
            return internal_error(error)

    return generate_response('calibrate_camera', 'calibrate/camera.html')



@app.route('/main/<action>', methods=['GET', 'POST'])
def main(action):
    if request.method == 'GET':
        if action == "soldermask":
            template = "soldermask.html"
        elif action == "gcode":
            template = "gcode.html"
        #elif action == "index":
        #    template = "main.html"
        else:
            abort(404)
        return generate_response('main', template)
    elif request.method == 'POST':
        if 'pcb_drill_session' not in session:
                print "Invalid session, redirecting to index"
                return redirect(url_for("index"))
        if action == "soldermask":
            if 'image' in request.files:
                f = request.files['image']
                filename = IMAGE_STORAGE + "/" + session['pcb_drill_session'] + "solder_mask_original_" + secure_filename(f.filename)
                f.save(filename)
                try:
                    message = send_command('process_solder_mask', filename=session['pcb_drill_session'] +
                                             "solder_mask_original_" +
                                                secure_filename(f.filename))
                except DaemonError as error:
                    return internal_error(error)
                data = message['output']
                prefix_rows = len(data['prefix'].splitlines())
                postfix_rows = len(data['postfix'].splitlines())
                body_rows = len(data['body'].splitlines())
                cv_solder_mask_filename=url_for('static', filename='pcb_drill_image_library/' + os.path.basename(data['cv_solder_mask_filename']))
                return generate_response('main', 'soldermask.html',prefix=data['prefix'], postfix=data['postfix'],
                            gcode=data['gcode'], count=data['count'],body=data['body'],
                            cv_solder_mask_filename=cv_solder_mask_filename,
                            holes=data['holes'], prefix_rows=prefix_rows, postfix_rows=postfix_rows, body_rows=body_rows) 
            else:
                print "No file"
        elif action == "gcode":
            gcode = StringIO.StringIO()
            gcode.write(request.form.get("prefix"))
            gcode.write(request.form.get("body"))
            gcode.write(request.form.get("postfix"))
            return gcode.getvalue()
    else:
        raise NotImplementedError("Error not here")

@app.route('/library/')
@app.route('/library/<filename>')
def library(filename=""):
    # TODO validate the filename, handle IOError, etc for writing file.
    # Security tip: Don't use os.path.join as it will follow ../
    gcode = None
    max_rows = 5
    if filename != "":
        fullpath = GCODE_LIBRARY + os.path.sep + filename
    else:
        fullpath = ""

    dir_list = []
    for dirname, dirnames, filenames in os.walk(GCODE_LIBRARY):
        for name in filenames:
            if name.lower().endswith(".gcode"):
                dir_list.append(name)
    print "dir_list: ", dir_list

    # These are special files that are generated on the fly.
    if filename == "calibrate_printer.gcode":
        # This is a special file that we use to generate the calibration holes
        if not os.path.exists(fullpath):
            # It is magicial since it will be auto generated as needed
            gcode = calibrate_printer(line_numbers=False)
            with open(fullpath, "w") as write_file:
                write_file.write(gcode)
    elif filename == "eject_bed.gcode":
        if not os.path.exists(fullpath):
            gcode = eject_bed(line_numbers=False)
            with open(fullpath, "w") as write_file:
                write_file.write(gcode)
    elif filename == "retract_bed.gcode":
        if not os.path.exists(fullpath):
            gcode = retract_bed(line_numbers=False)
            with open(fullpath, "w") as write_file:
                write_file.write(gcode)
    try:
        if fullpath != "":
            with open(fullpath, "r") as open_file:
                gcode = open_file.read()
                max_rows = len(gcode.splitlines())
            
    except IOError as exception:
        print "IOError:", exception
        abort(404)
    return generate_response('library', 'library.html', gcode=gcode,
                            filename=filename, max_rows=max_rows,
                            fullpath=fullpath, dir_list=dir_list)

@app.route('/about')
def about():
    return generate_response('about', 'about.html')

@app.route('/octoprint')
def octoprint():
    abort(404) 

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "PCB Drill Web Interface")
    parser.add_argument('--debug',action='store_true', help="Enables debug mode")
    parser.add_argument('--config', help="Specify configuration file",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "../pcb_drill.ini"))
    args = parser.parse_args()
    app.debug = args.debug

    config_parser = ConfigParser.ConfigParser()
    config_parser.read(args.config)
    IMAGE_STORAGE = config_parser.get('web', 'image_storage')
    GCODE_LIBRARY = config_parser.get('web', 'gcode_library')

    for dirname in (IMAGE_STORAGE, GCODE_LIBRARY):
        if not os.path.exists(dirname):
            print "We are going to stop here because an essential directory does not exist as specified in ",
            print args.config
            print "Please mkdir {0} or change the entry in the config file".format(dirname)
            exit(1)
    random.seed()
    # Cookies are only valid per startup session. And this isn't cryptographically secure...
    app.secret_key = "".join([chr(random.randrange(ord('A'), ord('z'))) for i in range(40)])
    app.run(host='0.0.0.0', port=int(config_parser.get('web', 'port'))) 
