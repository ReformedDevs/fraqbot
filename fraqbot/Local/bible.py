from Legobot.Lego import Lego
import logging
import requests

logger = logging.getLogger(__name__)

class Bible(Lego):
	def listening_for(self, message):
		return message['text'].split()[0] == '!bible'

	def handle(self, message):
		try:
			target = message['metadata']['source_channel']
			opts = {'target': target}
		except IndexError:
			logger.error('''Could not identify message source in message:
						{}'''.format(str(message)))

		base_url = 'https://bible-api.com/'
		passage = message['text'].replace(
					message['text'].split()[0], '').strip()

		r = requests.get(base_url + passage)

		if r.status_code == requests.codes.ok:
			reference = r.json()['reference']
			text = r.json()['text']
			self.reply(message, reference + ':\n' + text, opts)
		else:
			logger.error('Requests encountered an error.')
			logger.error('''HTTP GET response code:
						{}'''.format(r.status_code))

	def get_name(self):
		return 'Bible'

	def get_help(self):
		help_text = ('Get Bible references using bible-api.com. ' 
					'All text uses the WEB translation. ' 
					'Usage: !bible <book> <chapter>:<verse(s)>'
					'Checkout github.com/pard68/legos.bible for more info')
		return help_text

