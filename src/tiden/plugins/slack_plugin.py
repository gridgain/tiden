#!/usr/bin/env python3
#
# Copyright 2017-2020 GridGain Systems.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from tiden.tidenplugin import TidenPlugin
from tiden.util import json_request, log_print
from urllib.parse import quote
from os import environ
from subprocess import check_output

TIDEN_PLUGIN_VERSION = '1.0.0'

# For use - add down lines to default-plugins.yaml
# SlackPlugin:
# print_results: True
# direct_message: user / channel
# direct_name: 'username' / ' channelname'


class SlackPlugin(TidenPlugin):
    # default behaviour is to print log during whole test run
    correct_init = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.predicate = '@' if self.options.get('direct_message', 'user') == 'user' else ''
        self.bot_name = self.options.get('bot_name', 'TidenSlackBot')
        self.slack_token = self.options.get('slack_token')

    def before_hosts_setup(self, *args, **kwargs):
        self.correct_init = False
        auth_info = self.auth()
        if not 'user' in auth_info:
            log_print('Not correct SLACK_TOKEN to auth, please verify, receive token - {}'.format(self.slack_token),
                      color='red')
            self.correct_init = False
            return
        self.user = self.options.get('direct_name', auth_info['user'])
        self.correct_init = True
        self.log_print(
            "Connect to Slack complete, bot_name - {}, append to {}{}".format(self.bot_name, self.predicate, self.user))
        build_log = environ.get('BUILD_URL', False)
        self.build_log_format = "[{\"text\":\"Ver: %s, Log: %s\"}]" % (
            environ.get('IGNITE_VERSION', 'undef'),
            '{}console'.format(build_log) if build_log else 'local-run')
        self.git_branch_name = environ.get('BRANCH', 'undef')
        if self.git_branch_name == 'undef':
            try:
                self.git_branch_name = check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode(
                    "utf-8").rstrip()
            except:
                self.git_branch_name = None

    def auth(self):
        url_request = "https://slack.com/api/auth.test?" \
                      "token={}&" \
                      "pretty=1".format(self.slack_token)
        return json_request(url_request)

    def send_to_user(self, message):
        url_request = "https://slack.com/api/chat.postMessage?" \
                      "token={}&" \
                      "channel={}{}&" \
                      "text={}&" \
                      "username={}&" \
                      "attachments={}&" \
                      "pretty=1".format(self.slack_token, self.predicate, self.user, quote(message, safe=''),
                                        self.bot_name, quote(self.build_log_format, safe=''))
        json_request(url_request)

    def after_tests_run(self, *args, **kwargs):
        if len(args) > 1 and self.correct_init:
            if self.options.get('print_results', False):
                self.send_to_user(
                    "Branch: *{}*, Suite *{}* run with results - {}".format(
                        self.git_branch_name, ','.join(args[0].keys()), args[1].get_summary()))
        pass
