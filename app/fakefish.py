#!/usr/bin/env python3
# coding=utf-8

import flask
import json
import os
import requests
import subprocess
from datetime import datetime
from werkzeug.http import parse_authorization_header
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

app = flask.Flask(__name__)

try:
    app.config.from_object('settings')
    config = app.config
except ImportError:
    config = {'PORT': os.environ.get('PORT', 9000)}

debug = bool(config['DEBUG']) if 'DEBUG' in list(config) else False
port = int(config['PORT']) if 'PORT' in list(config) else 9000

@app.route('/redfish/v1/')
def root_resource():
    return flask.render_template('root.json')

@app.route('/redfish/v1/Managers')
def manager_collection_resource():
    return flask.render_template('managers.json')

@app.route('/redfish/v1/Systems')
def system_collection_resource():
    return flask.render_template('systems.json')

@app.route('/redfish/v1/Systems/1', methods=['GET', 'PATCH'])
def system_resource():
    username, password = get_credentials(flask.request)
    global bmc_ip
    if flask.request.method == 'GET':
       return flask.render_template(
           'fake_system.json',
           power_state=power_state,
        )
    else:
       app.logger.info('patch request') 
       boot = flask.request.json.get('Boot')
       if not boot:
           return ('PATCH only works for Boot'), 400
       if boot:
           target = boot.get('BootSourceOverrideTarget')
           mode = boot.get('BootSourceOverrideMode')
           if not target and not mode:
               return ('Missing the BootSourceOverrideTarget and/or '
                       'BootSourceOverrideMode element', 400)
           else:
               app.logger.info('Running script that sets boot from VirtualCD once')
               try:
                   subprocess.check_call(['custom_scripts/bootfromcdonce.sh', bmc_ip, username, password])
               except subprocess.CalledProcessError as e:
                   return ('Failed to set boot from virtualcd once', 400)

               return '', 204

@app.route('/redfish/v1/Systems/1/EthernetInterfaces', methods=['GET'])
def manage_interfaces():
    return flask.render_template('fake_interfaces.json')

@app.route('/redfish/v1/Managers/1', methods=['GET'])
def manager_resource():
    return flask.render_template(
           'fake_manager.json',
           date_time=datetime.now().strftime('%Y-%M-%dT%H:%M:%S+00:00'),
        )

@app.route('/redfish/v1/Systems/1/Actions/ComputerSystem.Reset',
           methods=['POST'])
def system_reset_action():
    global bmc_ip
    username, password = get_credentials(flask.request)
    reset_type = flask.request.json.get('ResetType')
    global power_state 
    if reset_type == 'On':
        app.logger.info('Running script that powers on the server')
        try:
            subprocess.check_call(['custom_scripts/poweron.sh', bmc_ip, username, password])
        except subprocess.CalledProcessError as e:
            return ('Failed to poweron the server', 400)
        power_state = 'On'
    else:
        app.logger.info('Running script that powers off the server')
        try:
            subprocess.check_call(['custom_scripts/poweroff.sh', bmc_ip, username, password])
        except subprocess.CalledProcessError as e:
            return ('Failed to poweroff the server', 400)
        power_state = 'Off'

    return '', 204


@app.route('/redfish/v1/Managers/1/VirtualMedia', methods=['GET'])
def virtualmedia_collection_resource():
    return flask.render_template('virtualmedias.json')

@app.route('/redfish/v1/Managers/1/VirtualMedia/Cd', methods=['GET'])
def virtualmedia_cd_resource():
    return flask.render_template(
        'virtualmedia_cd.json',
        inserted=inserted,
        image_url=image_url,
        )

@app.route('/redfish/v1/Managers/1/VirtualMedia/Cd/Actions/VirtualMedia.InsertMedia',
          methods=['POST'])
def virtualmedia_insert():
    global bmc_ip
    username, password = get_credentials(flask.request)
    image = flask.request.json.get('Image')
    if not image:
        return('POST only works for Image'), 400
    else:
        global inserted
        global image_url
        inserted = True
        image_url = image
        app.logger.info('Running script that mounts cd with iso %s', image)
        try:
            subprocess.check_call(['custom_scripts/mountcd.sh', bmc_ip, username, password, image_url])
        except subprocess.CalledProcessError as e:
            return ('Failed to mount virtualcd', 400)
        return '', 204

@app.route('/redfish/v1/Managers/1/VirtualMedia/Cd/Actions/VirtualMedia.EjectMedia',
          methods=['POST'])
def virtualmedia_eject():
    global bmc_ip
    username, password = get_credentials(flask.request)
    global inserted
    global image_url
    inserted = False
    image_url = ''
    app.logger.info('Running script that unmounts cd')
    try:
        subprocess.check_call(['custom_scripts/unmountcd.sh', bmc_ip, username, password])
    except subprocess.CalledProcessError as e:
        return ('Failed to unmount virtualcd', 400)
    return '', 204


def get_credentials(flask_request):
    auth = flask_request.headers.get('Authorization', None)
    username = ''
    password = ''
    if auth is not None:
        creds = parse_authorization_header(auth)
        username = creds.username
        password = creds.password
    app.logger.debug('Returning credentials')
    app.logger.debug('Username: ' + username + ', password: ' + password)
    return username, password

def run():
    """

    """
    app.run(host='0.0.0.0', port=port, debug=debug, ssl_context='adhoc')


if __name__ == '__main__':

    inserted = False
    image_url = ''
    power_state = 'On'
    bmc_ip = os.environ.get('BMC_IP', None)
    if bmc_ip is not None:
        app.logger.info(bmc_ip)
    else:
        app.logger.error('Configure the BMC IP using the environment variable BMC_IP')
        exit()
    run()
