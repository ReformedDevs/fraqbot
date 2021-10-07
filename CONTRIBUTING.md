# Contributing to fraqbot

Thanks for your interest in contributing to fraqbot. He needs all the help he can get. =)

## What should I know before I get started?

**fraqbot** is built on the [Legobot](https://github.com/Legobot/Legobot) framework, a multi-provider chatbot framework written in [Python 3](https://python.org).

Legobot relays messages from a Connector (a module that reads and replies to messages over socket connection with the chat provider) to modules, called Legos. Each Lego can then process the message, decide what to do with it, and send reply back to the Connector, which will relay it appropriately to the chat.

This particular implementation of Legobot is specific to The Reformed Devs Slack org, and as such has some custom hackery going on, such as calling the Slack API for special uses instead of just replying to the Connector. Most of the Local legos are not fit to be used outside of a Slack connection.

## Repo Structure

### Meta

The root level of the repo contains all the meta information -- python dev requirements, docs, utility configs, etc.

### The App

In the [fraqbot/](./frabot/) directory is the nuts and bolts of the app. There are 4 main components:

#### Docker

The [Dockerfile](./fraqbot/Dockerfile) containerizes the app.

#### Chatbot

The [chatbot.py](./fraqbot/chatbot.py) file loads the config and runs the modules.

#### Local

[Local](./fraqbot/Local/) contains all the locally developed (i.e. not published on pypi) Legos used in fraqbot.

#### Tests

The [tests](./fraqbot/tests/) driectory contains the unit tests for the local legos.

## Development

### Philosophy

This is a fairly standard Python app, though its creator is somewhat opinionated on philosophy and style. Here some things to keep in mind:

* Philosophy
  * Comprehensions are beautiful and efficient.
  * Explicit is better than implicit.
  * Python scoping is weird. Don't use non-global variables where they aren't explicitly scoped, even if it "works."
  * Make it human readable.
  * If you think it might not be clear what your code does, add a comment.
  * Keep functions small.
  * Don't be afraid to think outside the (Legobot) box.
  * Got some reusable functionality? Put it in helpers.py!
  * Feel free to refactor for cleanliness, efficiency, and readability.
* Style
  * We use **[flake8](https://flake8.pycqa.org/en/3.8.4/)** for linting, with the **[hacking](https://docs.openstack.org/hacking/latest/user/index.html)** extensions/preferences from Red Hat. Check [requirements-dev.txt](./requirements-dev.txt) for versions. If your build fails the linting check it won't be merged.
  * No, you cannot add a .flake8 or tox.ini file to change linting behavior. Sorry, `¯\_(ツ)_/¯`
  * Imports should be sorted alphabetically according to flake8 style, and in (up to) 4 sections (See [aoc.py](./fraqbot/Local/aoc.py) for a good example of all 4 sections.):
    1. "Standard" libraries and modules
    2. 3rd party imports
    3. Legobot items
    4. Local items.
  * Class methods that do not extend existing methods from the parent class should be prefixed with `_`.
  * Quotes: Always use single quotes unless you have to escape more than once in the string.
  * F-strings are preferred over all other string interpolation methods. `.format` is acceptable if f-strings are cumbersome or won't work (for example when referencing dictionary values by key). `%` interpolation is right out.
  * Multi-line strings should be concatenated by implication with parentheses. Do not use `+`.
  * Code blocks (condition blocks, loops, try/except, etc.) should be visually separated from their surrounding code.

### Setting up your environment

1. Install Python 3 if you haven't already, specifically 3.8.5 as that's what fraqbot runs on.
2. Clone the repo.
   1. `git clone https://github.com/ReformedDevs/fraqbot && cd fraqbot`
3. Install the requirements.
   1. `pip install -r requirements-dev.txt`
      * This installs both the dev requirements and the app requirements.
   2. (*Optional*) Install the the Legobot **blocks** branch. Assuming you are in the fraqbot repo directory:

   ```sh
      git clone https://github.com/Legobot/Legobot ../Legobot
      cd ../Legobot
      git checkout blocks
      cd ../fraqbot
      pip install -e ../Legobot/.
      ```

      * This installs Legobot locally with the as yet unreleased "blocks" feature. This feature is currently only used by the local [XKCD](./fraqbot/Local/xkcd.py) Lego.
4. Create a config file.
   * If you are going to actually run the chatbot, you need a `config.yaml` file in the same directory as [chatbot.py](./fraqbot/chatbot.py).
   * You will need a Slack API token for this.
   * See the [Example Config](./fraqbot/example-config.yaml).

### Adding a new Lego

Each new Lego should be in its own file in Local. The Lego code itself is a subclass of `Legobot.Lego.Lego`. At bare minumim you need a `listening_for` method and a `handle` method. When you want to send a reply from your Lego back to the original message, use the `reply` method. Below is a description of the built in Lego methods and how to overwrite them.

#### `__init__`

Obviously this is the initialization of the class. If you don't need to import an acl or other kwargs, overriding this method is not necessary. An override example:

```python
def __init__(self, baseplate, lock, *args, **kwargs):
    super().__init__(baseplate, lock, acl=kwargs.get('acl'))
    # insert other initialization here
```

#### `listening_for`

This is the method that determines if your Lego should take action on a message. Every message from the stream goes through it. If it returns `True` then the Lego executes the `handle` method. Example:

```python
def listening_for(self, message):
    text = message.get('text')
    return isinstance(text, str) and text.lower().startswith('moin')
```

#### `handle`

The `handle` method is invoked if `listening_for` returns `True`. Use it to orchestrate logic and various pieces of functionality, then return a response to the Connector. Typically, you will use the `build_reply_opts` method (not overridden) to set the options of how to reply and the `reply` method (not overridden) to send the reply. `build_reply_opts` will automatically configure your reply to go to the originating channel or dm, and within a thread if the handled message was in a thread. Example:

```python
def handle(self, message):
    response = self._some_method_to_create_a_response(message)
    if response:
        opts = self.build_reply_opts(message)
        self.reply(message, response, opts)
```

#### `get_name`

The `get_name` method returns the name of the Lego. It is not required. If you don't include this method the Lego will not be listed by the generic `!help` command. Example:

```python
def get_name(self):
    return 'TuRD Lego'
```

#### `get_help`

The `get_help` method returns help text when invoked by the `!help <Lego Name>` command. It is also not required. Example:

```python
def get_help(self):
    return 'Type `!some_command` to get some_response back.'
```

### Testing

#### Linting and security tests

You can invoke the linting tests with:

```sh
python -m flake8 fraqbot
```

You can invoke the security tests with:

```sh
python -m bandit --ini .bandit
```

#### Unit tests

We use pytest for running unit tests. You can add your own tests for Legos in the [fraqbot/tests](./fraqbot/tests/) directory.
To invoke a Lego for testing, you can use something like this:

```python
LOCK = threading.Lock()
BASEPLATE = Lego.start(None, LOCK)
LEGO = YourLegoClass(BASEPLATE, LOCK, **any_kwargs)
```

Then, in your tests, you can call your various methods with `LEGO.method_name()`.

Run all unit tests with:

```sh
python -m pytest -v
```

## Getting help

* Come hang out in **#bot-bable** in The Reformed Devs Slack.
