# Copyright (c) 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import requests
import testresources
import testtools
import time
import uuid

from glanceclient import Client as gclient
from keystoneclient.v2_0 import client as ksclient

import functionaltests.engine.config as cfg


CONF = cfg.cfg.CONF


class Client(object):

    def __init__(self, user, password, tenant, auth_url):

        self.auth = ksclient.Client(username=user, password=password,
                                    tenant_name=tenant, auth_url=auth_url)

        self.endpoint = self.auth.service_catalog.url_for(
            service_type='application_catalog', endpoint_type='publicURL')

        self.headers = {
            'X-Auth-Token': self.auth.auth_token,
            'Content-type': 'application/json'
        }

        glance_endpoint = \
            self.auth.service_catalog.url_for(service_type='image',
                                              endpoint_type='publicURL')
        glance = gclient('1', endpoint=glance_endpoint,
                         token=self.auth.auth_token)

        for i in glance.images.list():
            if 'murano_image_info' in i.properties.keys():
                if 'linux' == json.loads(
                        i.properties['murano_image_info'])['type']:
                    self.linux = i.name
                elif 'windows' in json.loads(
                        i.properties['murano_image_info'])['type']:
                    self.windows = i.name
                elif 'demo' in json.loads(
                        i.properties['murano_image_info'])['type']:
                    self.demo = i.name

    def create_environment(self, name):
        post_body = {'name': name}
        resp = requests.post(self.endpoint + 'environments',
                             data=json.dumps(post_body),
                             headers=self.headers)

        return resp.json()

    def delete_environment(self, environment_id):
        endpoint = '{0}environments/{1}'.format(self.endpoint, environment_id)
        return requests.delete(endpoint, headers=self.headers)

    def get_environment(self, environment_id):
        return requests.get('{0}environments/{1}'.format(self.endpoint,
                                                         environment_id),
                            headers=self.headers).json()

    def create_session(self, environment_id):
        post_body = None
        endpoint = '{0}environments/{1}/configure'.format(self.endpoint,
                                                          environment_id)

        return requests.post(endpoint, data=post_body,
                             headers=self.headers).json()

    def deploy_session(self, environment_id, session_id):
        endpoint = '{0}environments/{1}/sessions/{2}/deploy'.format(
            self.endpoint, environment_id, session_id)

        return requests.post(endpoint, data=None, headers=self.headers)

    def create_service(self, environment_id, session_id, json_data):
        headers = self.headers.copy()
        headers.update({'x-configuration-session': session_id})

        endpoint = '{0}environments/{1}/services'.format(self.endpoint,
                                                         environment_id)

        return requests.post(endpoint, data=json.dumps(json_data),
                             headers=headers).json()

    def status_check(self, environment_id):
        environment = self.get_environment(environment_id)
        start_time = time.time()
        while environment['status'] != 'ready':
            if time.time() - start_time > 1200:
                return
            time.sleep(5)
            environment = self.get_environment(environment_id)
        return 'OK'

    def deployments_list(self, environment_id):
        endpoint = '{0}environments/{1}/deployments'.format(self.endpoint,
                                                            environment_id)

        return requests.get(endpoint,
                            headers=self.headers).json()['deployments']


class MuranoBase(testtools.TestCase, testtools.testcase.WithAttributes,
                 testresources.ResourcedTestCase):

    @classmethod
    def setUpClass(cls):
        super(MuranoBase, cls).setUpClass()

        cls.client = Client(user=CONF.murano.user,
                            password=CONF.murano.password,
                            tenant=CONF.murano.tenant,
                            auth_url=CONF.murano.auth_url)

    def setUp(self):
        super(MuranoBase, self).setUp()

        self.environments = []

    def tearDown(self):

        for env in self.environments:
            try:
                self.client.delete_environment(env)
            except Exception:
                pass

    def test_deploy_telnet(self):
        post_body = {
            "instance": {
                "flavor": "m1.medium",
                "image": self.client.linux,
                "?": {
                    "type": "io.murano.resources.Instance",
                    "id": str(uuid.uuid4())
                },
                "name": "testMurano"
            },
            "name": "teMurano",
            "?": {
                "_{id}".format(id=uuid.uuid4().hex): {
                    "name": "Telnet"
                },
                "type": "io.murano.apps.linux.Telnet",
                "id": str(uuid.uuid4())
            }
        }

        environment = self.client.create_environment('Telnetenv')
        self.environments.append(environment['id'])

        session = self.client.create_session(environment['id'])

        self.client.create_service(environment['id'], session['id'], post_body)
        self.client.deploy_session(environment['id'], session['id'])

        status = self.client.status_check(environment['id'])

        self.assertEqual('OK', status)

        deployments = self.client.deployments_list(environment['id'])
        for deployment in deployments:
            self.assertEqual('success', deployment['state'])

    def test_deploy_apache(self):
        post_body = {
            "instance": {
                "flavor": "m1.medium",
                "image": self.client.linux,
                "?": {
                    "type": "io.murano.resources.Instance",
                    "id": str(uuid.uuid4())
                },
                "name": "testMurano"
            },
            "name": "teMurano",
            "?": {
                "_{id}".format(id=uuid.uuid4().hex): {
                    "name": "Apache"
                },
                "type": "io.murano.apps.apache.Apache",
                "id": str(uuid.uuid4())
            }
        }

        environment = self.client.create_environment('Apacheenv')
        self.environments.append(environment['id'])

        session = self.client.create_session(environment['id'])

        self.client.create_service(environment['id'], session['id'], post_body)
        self.client.deploy_session(environment['id'], session['id'])

        status = self.client.status_check(environment['id'])

        self.assertEqual('OK', status)

        deployments = self.client.deployments_list(environment['id'])
        for deployment in deployments:
            self.assertEqual('success', deployment['state'])