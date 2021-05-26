import logging
import os
import random
import re
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
                text.startswith('!newjob')))

    def _strip_and_parse_terms(self, term):
        term_split = [
            t.lower().strip() for t in
            term.split(',') if len(t.strip()) > 0
        ]
        if len(term_split) > 2:
            term_split[2] = re.sub('^at', '', term_split[2]).strip()
        return [
            # Role Modifier search term
            term_split[0],
            # Role search term
            term_split[1] if len(term_split) > 1 else term_split[0],
            # Company search term
            term_split[2] if len(term_split) > 2 else term_split[0],
        ]

    def _search_list(self, listname, term):
        return [string for string in getattr(self, f'{listname}_list') if
                term in string.lower()]

    def _get_job(self, term):

        found_mods = []
        found_roles = []
        found_companies = []

        if term:
            terms_parsed = self._strip_and_parse_terms(term)
            found_mods = self._search_list('role_modifiers', terms_parsed[0])
            found_roles = self._search_list('roles', terms_parsed[1])
            found_companies = self._search_list('companies', terms_parsed[2])

        extra_text = ('\n\n(No match for search term)'
                      if (term and
                          (not found_mods and
                           not found_roles and
                           not found_companies)) else '')

        if not found_mods:
            found_mods = self.role_modifiers_list
        if not found_roles:
            found_roles = self.roles_list
        if not found_companies:
            found_companies = self.companies_list

        random_company = random.choice(found_companies)

        final_string = ' '.join([
            random.choice(found_mods),
            random.choice(found_roles),
            'at',
            ('{} (<https://en.wikipedia.org/wiki/{}' +
                '|en.wikipedia.org/wiki/{}>)').format(
                    random_company,
                    random_company.replace(' ', '_'),
                    random_company.replace(' ', '_')
                ),
            extra_text
            ])

        return final_string

    def handle(self, message):
        logger.debug('Handling NewJob request: {}'.format(message['text']))
        text_split = message['text'].split(maxsplit=1)
        term = text_split[1].strip() if len(text_split) > 1 else None

        new_job = self._get_job(term)
        opts = self.build_reply_opts(message)
        self.reply(message, new_job, opts)

    def get_name(self):
        return 'New_Job'

    def get_help(self):
        return ('Take the next illogical step in your failing career! ' +
                'Usage: !job [optional:<keyword/term>]')
