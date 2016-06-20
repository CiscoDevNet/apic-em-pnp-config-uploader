#!/usr/bin/env python

################################################################################
#                                                                              #
# Copyright (c) 2015 Cisco Systems                                             #
# All Rights Reserved.                                                         #
#                                                                              #
#    Licensed under the Apache License, Version 2.0 (the "License"); you may   #
#    not use this file except in compliance with the License. You may obtain   #
#    a copy of the License at                                                  #
#                                                                              #
#         http://www.apache.org/licenses/LICENSE-2.0                           #
#                                                                              #
#    Unless required by applicable law or agreed to in writing, software       #
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT #
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the  #
#    License for the specific language governing permissions and limitations   #
#    under the License.                                                        #
#                                                                              #
################################################################################

#AUTHOR: Tobias Huelsdau, <thulsdau@cisco.com>
#VERSION 2016.06.18.a

APIC_BASE_URL = 'https://%s:443/api/v1/'
DEBUG = True
GLOBAL_PARAMS = {}
#Auth ticket for subsqeuent calls after login
TICKET = None

import argparse
import mimetypes
import random
import string
import json, os, sys, os.path, re, time
from pprint import pprint

import ssl
#monkeypath ssl to accept every cert, see https://bugs.python.org/issue22417
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass
    
#Handle different urllib version on Python 3.x vs. 2.x
try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

def print_debug(text):
    if type(text) != type(''):
        text = str(text)
    if DEBUG:
        sys.stderr.write(text)
        sys.stderr.write('\n')

def apic_connect(url,method="GET",data=None,header='application/json'):
    handler = urllib2.HTTPHandler()
    opener = urllib2.build_opener(handler)
    request = urllib2.Request(url,data)
    if type(header) == type(''):
        request.add_header("Content-Type",header)
    else:
        for name, value in header.items():
            request.add_header(name,value)
    request.get_method = lambda: method
    if TICKET:
        request.add_header('X-Auth-Token',TICKET)
    try:
        connection = opener.open(request)
    except urllib2.HTTPError as e:
        connection = e
    data = connection.read()
    connection.close()
    try:
        response = json.loads(data)
    except:
        print_debug(data)
        raise
    return response

def encode_multipart(fields, files, boundary=None):
    r"""Encode dict of form fields and dict of files as multipart/form-data.
    Return tuple of (body_string, headers_dict). Each value in files is a dict
    with required keys 'filename' and 'content', and optional 'mimetype' (if
    not specified, tries to guess mime type or uses 'application/octet-stream').

    Copied from: http://code.activestate.com/recipes/578668-encode-multipart-form-data-for-uploading-files-via/
    """
    _BOUNDARY_CHARS = string.digits + string.ascii_letters
    def escape_quote(s):
        return s.replace('"', '\\"')
    if boundary is None:
        boundary = ''.join(random.choice(_BOUNDARY_CHARS) for i in range(30))
    lines = []
    for name, value in fields.items():
        lines.extend((
            '--{0}'.format(boundary),
            'Content-Disposition: form-data; name="{0}"'.format(escape_quote(name)),
            '',
            str(value),
        ))
    for name, value in files.items():
        filename = value['filename']
        if 'mimetype' in value:
            mimetype = value['mimetype']
        else:
            mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        lines.extend((
            '--{0}'.format(boundary),
            'Content-Disposition: form-data; name="{0}"; filename="{1}"'.format(
                    escape_quote(name), escape_quote(filename)),
            'Content-Type: {0}'.format(mimetype),
            '',
            value['content'],
        ))
    lines.extend((
        '--{0}--'.format(boundary),
        '',
    ))
    body = '\r\n'.join(lines)
    headers = {
        'Content-Type': 'multipart/form-data; boundary={0}'.format(boundary),
        'Content-Length': str(len(body)),
    }
    return (body, headers)

def login(username,password):
    URL = APIC_URL + 'ticket'
    logindata = json.dumps({'username':username,'password':password})
    response = apic_connect(URL, "POST", logindata)
    ticket = response['response']['serviceTicket']
    return ticket

def get_siteID(siteName):
    """Get ID of ZTD site by site name from APIC-EM ZTD Module"""
    URL = APIC_URL + 'pnp-project?siteName=%s&offset=1&limit=500' % siteName
    response = apic_connect(URL)
    response = response['response']
    for site in response:
        if siteName == site['siteName']:
            return site['id']
    return None

def get_all_sites():
    """Return list of all sites present in APIC-EM"""
    URL = APIC_URL + 'pnp-project?offset=1&limit=500'
    response = apic_connect(URL)
    response = response['response']
    sites = {}
    for site in response:
        sites[site['siteName']] = site
    return sites

def create_site(siteName):
    """Create new ZTD Site"""
    URL = APIC_URL + 'pnp-project'
    data = [{'siteName':siteName}]
    json_data = json.dumps(data)
    response = apic_connect(URL,'POST',json_data)
    response = response['response']
    #Retrieve site with all data
    URL = APIC_URL + 'pnp-project?siteName=%s&offset=1&limit=500' % siteName
    response = apic_connect(URL)
    response = response['response']
    for site in response:
        return site

def upload_config(fileName,config,configID=None):
    """Upload config as fileName to APIC-EM, return ID"""
    URL = APIC_URL + 'file/config'
    verb = "POST"
    fileName = os.path.basename(fileName)    
    if configID:
        URL = URL + '/' + configID
        verb = "PUT"
    fields = {'configPreference': fileName} 
    files = {'fileUpload': {'filename': fileName, 'content': config, 'mimetype':'text/plain'}}
    data, headers = encode_multipart(fields, files)
    response = apic_connect(URL, verb, data, headers)
    response = response['response']
    return response['id']

def get_all_images():
    """Get list of all IOS images imported into APIC-EM"""
    # URL changed in 1.1
    # old: URL = APIC_URL + 'file/image/file-list'
    URL = APIC_URL + 'file/namespace/image'
    response = apic_connect(URL)
    response = response['response']
    images = {}
    for image in response:
        images[image['name']] = image
    return images
    

def create_ZTD_rule(projectID, siteName, serialNumber, deviceName, productID, configID, imageID=None):
    """Create a new ZTD rule/device in APIC-EM, return TaskId and TaskURL"""
    URL = APIC_URL + 'pnp-project/%s/device' % projectID
    data = [{"hostName": deviceName,"serialNumber": serialNumber, 
            "platformId": productID,"site": siteName, "configId": configID, "pkiEnabled": False}]
    if imageID:
        data['imageId'] = imageID
    json_data = json.dumps(data)
    response = apic_connect(URL,'POST',json_data)
    response = response['response']
    if response.has_key('errorCode'):
        print_debug('  Error creating ZTD rule: %s' % response.get('detail',''))
    return response['taskId'],response['url']

def update_ZTD_rule(projectID, deviceID, updateData):
    """Update ZTD rule"""
    URL = APIC_URL + 'pnp-project/%s/device' % projectID
    updateData['id'] = deviceID
    json_data = json.dumps([updateData])
    response = apic_connect(URL,'PUT',json_data)
    response = response['response']
    return response['taskId'],response['url']

def delete_ZTD_rule(projectID,deviceID):
    """Delete a ZTD rule/device"""
    URL = APIC_URL + '/pnp-project/%s/device/%s' % (projectID,deviceID)
    response = apic_connect(URL,'DELETE')

def get_all_devices(projectID):
    """Get all devices stored under siteID"""
    URL = APIC_URL + 'pnp-project/%s/device?offset=1&limit=500' % projectID
    response = apic_connect(URL)
    response = response['response']
    serialNumbers = {}
    devices = {}
    for device in response:
        serialNumbers[device['serialNumber']] = device['hostName']
        devices[device['hostName']] = device
    return serialNumbers,devices

def delete_all_devices_in_site(siteName):
    """Delete all devices in a Site"""
    projectID = get_siteID(siteName)
    URL = APIC_URL + 'pnp-project/%s/device?offset=1&limit=500' % projectID
    response = apic_connect(URL)
    response = response['response']
    for device in response:
        delete_ZTD_rule(projectID,device['id'])

def get_all_configs():
    """Get names and fileIDs of all configs stored in APIC-EM"""
    URL = APIC_URL + 'file/namespace/'
    response = apic_connect(URL)
    response = response['response']
    #check if 'config' name-space exists. if not, return empty dict
    try:
        response.index('config')
    except ValueError:
        return {}
    # URL changed in 1.1
    # old: URL2 = APIC_URL + 'file/config/file-list'
    URL2 = APIC_URL + 'file/namespace/config'
    response = apic_connect(URL2)
    response = response['response']
    configs = {}
    for config in response:
        configs[config['name']] = config['id']
    return configs

def delete_all_configs():
    """Delete all (ZTD) configs from APIC-EM"""
    URL = APIC_URL + 'file/file/%s'
    configs = get_all_configs()
    for fileName in configs.keys():
        print_debug('Deleting config file %s.' % fileName)
        response = apic_connect(URL % configs[fileName],'DELETE')

def check_task(taskID):
    """Get status of task"""
    URL = APIC_URL + 'task/' + taskID
    response = apic_connect(URL)
    response = response['response']
    return response

def search_config(config,param):
    match = re.search('^%s (\S+)\r?$' % param,config, re.MULTILINE)
    return match.group(1)

def iterate_files_and_dirs(files_or_paths):
    for my_file in files_or_paths:
        if os.path.isdir(my_file):
            for file_in_dir in os.listdir(my_file):
                if file_in_dir.endswith('.txt'):
                    yield((my_file,file_in_dir))
        else:
            if my_file.endswith('.txt'):
                yield(('',my_file))
            else:
                print_debug("File %s doesn't end in .txt, ignoring." % my_file)

def main(params):
    """Search path for files ending in .cfg.txt, upload them and create corresponding ZTD rule"""
    sites_seen = {}
    devices_in_site = {}
    configs_in_apic = get_all_configs()
    sites_in_apic = get_all_sites()
    images_in_apic = get_all_images()
    tasks = []
    error_counter = 0
    for (path,my_file) in iterate_files_and_dirs(params['filelist']):
        fd = open(os.path.join(path,my_file),'r')
        file_content = fd.read()
        hostname = search_config(file_content,'hostname')
        serial = search_config(file_content,'! SERIAL')
        site = search_config(file_content,'! SITE')
        model = search_config(file_content,'! MODEL')
        taskData = {'hostname':hostname,'serial':serial,'site':site,'model':model}
        image = None
        imageID = None
        try:
            image = search_config(file_content,'! IMAGE')
        except:
            pass
        if image:
            taskData['image'] = image
            imageID = images_in_apic.get(image,{}).get('id',None)
            if not imageID:
                print_debug('Image %s not found in APIC-EM for device %s' % (image,hostname))
                image = None
        # if this is the first config for a site, delete all devices in it first
        if not sites_seen.get(site,False):
            sites_seen[site] = True
            # create new site if it doesn't exist yet
            if not sites_in_apic.get(site,False):
                print_debug('Creating new site %s' % site)
                sitedata = create_site(site)
                sites_in_apic[site] = sitedata
                devices_in_site[site] = ({},{})
            else:
                # get all devices already present in site
                devices_in_site[site] = get_all_devices(sites_in_apic[site]['id'])
            if params['clear_site']:
                print_debug('Deleting all devices in site %s' % site)
                delete_all_devices_in_site(site)
                devices_in_site[site] = ({},{})
        print_debug('%s: Uploading config %s for device %s (%s)' % (site,my_file,hostname, serial))
        #if my_file already exists in configs then re-upload under same id, else upload new config
        configID = configs_in_apic.get(my_file,None)
        configID = upload_config(my_file,file_content,configID)
        projectID = sites_in_apic[site]['id']
        if devices_in_site[site][0].get(serial) == hostname:
            print_debug('  Device already exists in APIC-EM')
        elif devices_in_site[site][0].get(serial) and devices_in_site[site][0].get(serial) != hostname:
            print_debug('  Updating hostname for device')
            old_hostname = devices_in_site[site][0][serial]
            print_debug('  Old hostname: %s' % old_hostname)
            deviceID = devices_in_site[site][1][old_hostname]['id']
            taskID, taskURL = update_ZTD_rule(projectID,deviceID,{'hostName':hostname})
            taskData['taskID'] = taskID
            tasks.append(taskData)
        else:
            if devices_in_site[site][1].get(hostname):
                print_debug('  New serial number for hostname, deleting old entry')
                delete_ZTD_rule(devices_in_site[site][1][hostname]['id'])
            taskID, taskURL = create_ZTD_rule(projectID, site, serial, hostname, model, configID, imageID)
            taskData['taskID'] = taskID
            tasks.append(taskData)
    #Check if tasks were successfull
    if tasks:
        print_debug('### Uploading done. Checking APIC-EM tasks ###')
        time.sleep(3)
    for task in tasks:
        print_debug('Checking task for device %s (%s) in site %s...' % (task['hostname'],task['serial'],task['site']))
        response = check_task(taskID)
        try:
            progress = json.loads(response['progress'])
        except:
            progress = response['progress']
        if type(progress) == type({}) and progress.get('message'):
            progress = progress.get('message')
        print_debug('  Progress: %s' % progress)
        if response.get('isError',False):
            print_debug('  Failure: %s' % response['failureReason'])
            error_counter += 1
    return error_counter

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upload configs to APIC-EM and create corresponding ZTD rules.')
    parser.add_argument('-s','--server', required=True, help='Server hostname or IP of APIC-EM')
    parser.add_argument('-u','--username', required=True, help='Username to login to APIC-EM')
    parser.add_argument('-p','--password', required=True, help='Password to login to APIC-EM')
    parser.add_argument('-d','--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--clear-site', action='store_true', help='Clear all rules from site first')
    parser.add_argument('filelist',help='Config file(s) or path to config files (need to end in .txt)',default='.',nargs='*')
    args = parser.parse_args()
    for name,value in args._get_kwargs():
        GLOBAL_PARAMS[name] = value
    APIC_URL = APIC_BASE_URL % GLOBAL_PARAMS['server']
    TICKET = login(GLOBAL_PARAMS['username'],GLOBAL_PARAMS['password'])
    error_counter = main(GLOBAL_PARAMS)
    return_val = 0
    if error_counter:
        return_val = 1
    sys.exit(return_val)