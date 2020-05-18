FROM python:3

RUN mkdir /tmp/logs
WORKDIR /usr/src/app

# Get specific Legobot
# Only necessary if desired commit isn't available on pypi
# RUN git clone https://github.com/Legobot/Legobot
# WORKDIR /usr/src/app/Legobot
# RUN git checkout release-1.2.6
# RUN pip install -e .

# copy local stuff
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install -r ./requirements.txt
COPY . .
CMD python chatbot.py
