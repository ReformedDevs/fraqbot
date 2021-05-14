import logging
import os
import random
import sys

from Legobot.Lego import Lego


logger = logging.getLogger(__name__)
LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))

if LOCAL_DIR not in sys.path:
    sys.path.append(LOCAL_DIR)


import helpers as h  # noqa E402


class NewJob(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.role_modifiers_list = []
        self.roles_list = []
        self.companies_list = []
        role_modifiers = h.load_file(
            os.path.join(LOCAL_DIR, 'lists', 'role_modifiers.txt'), raw=True)
        roles = h.load_file(
            os.path.join(LOCAL_DIR, 'lists', 'roles.txt'), raw=True)
        companies = h.load_file(
            os.path.join(LOCAL_DIR, 'lists', 'companies.txt'), raw=True)

        if role_modifiers and roles and companies:
            self.role_modifiers_list = role_modifiers.splitlines()
            self.roles_list = roles.splitlines()
            self.companies_list = companies.splitlines()

    def listening_for(self, message):
        text = message.get('text')

        return (isinstance(text, str) and
            (text.startswith('!job') or
            text.startswith('!newjob'))

    def _get_job(self, term):

        found_role_modifiers = []
        found_roles = []
        found_companies = []

        if term:
            term_lowercase = term.lower()
            found_role_modifiers = [
                    phrase for phrase in
                    self.role_modifiers_list if term_lowercase in phrase
                ]
            found_roles = [
                    phrase for phrase in
                    self.roles_list if term_lowercase in phrase
                ]
            found_companies = [
                    phrase for phrase in
                    self.companies_list if term_lowercase in phrase
                ]

        if not found_role_modifiers:
            found_role_modifiers = self.role_modifiers_list
        if not found_roles:
            found_roles = self.roles_list
        if not found_companies:
            found_companies = self.companies_list

        random_company = random.choice(found_companies)

        final_string = ' '.join([
            'Congrats on the new role!',
            random.choice(found_role_modifiers),
            random.choice(found_roles),
            'at',
            '<https://en.wikipedia.org/wiki/{}|{}>'.format(
                    random_company.replace(' ', '_'),
                    random_company
                )
            ])

        return final_string

    def handle(self, message):
        logger.debug('Handling NewJob request: {}'.format(message['text']))
        term = message['text'].split(maxsplit=1)[1]

        new_job = self._get_job(term)
        opts = self.build_reply_opts(message)
        self.reply(message, new_job, opts)

    def get_name(self):
        return 'New_Job'

    def get_help(self):
        return 'Take the next illogical step in your failing career! Usage: !job [optional:<keyword/term>]'