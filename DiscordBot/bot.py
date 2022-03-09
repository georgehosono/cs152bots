# bot.py
import discord
from discord.ext import commands
from google_trans_new import google_translator
import os
import json
import logging
import re
import requests
from report import Report
import queue
from unidecode import unidecode
from nudenet import NudeClassifier
from PIL import Image
from io import BytesIO

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
#from uni2ascii import uni2ascii


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 2)

    def forward(self, x):
        print(x.shape)
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = torch.flatten(x, 1)  # flatten all dimensions except batch
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x


net = Net()
net = net.double()

HARRASMENT_THRESHOLD = 3.40
MAX_SCORE = 0.98
review_queue = queue.Queue(maxsize=100)
REVIEW_FLAG = False

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(
    filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter(
    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'token.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_key = tokens['perspective']


class ModBot(discord.Client):
    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {}  # Map from guild to the mod channel id for that guild
        self.reports = {}  # Map from user IDs to the state of their report
        self.perspective_key = key

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception(
                "Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply = "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to uss
        responses = await self.reports[author_id].handle_message(message)
        print(responses)
        for t in responses:
            print(t)
            r, m = tuple(t)
            if r[0] in ["You have chosen to hard-block the user. Thank you for taking the time to complete this report.", "You have chosen to soft-block the user. Thank you for taking the time to complete this report.", "Thank you for taking the time to complete this report."]:
                review_queue.put(m)
                k = list(self.mod_channels.keys())[0]
                await self.mod_channels[k].send('Added a flagged message to the queue') # ADDED
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):

        # Handle messages sent in the "group-29" channel
        if message.channel.name == f'group-{self.group_num}':
            await self.handle_group_29_channel_message(message)
        # Handle messages sent in the "group-29-mod" channel
        elif message.channel.name == f'group-{self.group_num}-mod':
            await self.handle_group_29_mod_channel_message(message)
        return

    async def handle_group_29_channel_message(self, message):
        #message.content = unidecode(message.content)

        flag = False
        if (len(message.attachments)) == 0:
            message.content = unidecode(message.content)
            translator = google_translator()
            message.content = translator.translate(
                message.content, lang_tgt='en')

            scores = self.eval_text(message)

            # Check if the message should be flagged
            flag = self.automatic_flagging(scores)
        else:  # ML!!!
            # manage if context.message.attachments is empty
            image_url = message.attachments[0].url
            # improve image format detection
            image_format_jpg = image_url[-3:]
            image_format_jpeg = image_url[-4:]
            if image_format_jpg.lower() == 'jpg' or image_format_jpeg.lower() == 'jpeg' or image_format_jpg.lower() == 'png':
                response = requests.get(image_url)
                img = Image.open(BytesIO(response.content))
                img = img.resize((32, 32))
                img_arr = np.asarray(img)[:,:,:3]
                img_arr = img_arr.transpose((2, 0, 1))
                pred = net(torch.from_numpy(img_arr).double().unsqueeze(0))
                print(pred.shape)
                print(pred)
                if float(pred[0,0]) > float(pred[0,1]):
                    flag = True

        # If the message is flagged, forward it to the queue of reported messages
        if flag is True:
            review_queue.put(message)
            mod_channel = self.mod_channels[message.guild.id]
            await mod_channel.send('Added a flagged message to the queue. Due to the confidence level in our automated flagging, this post will be taken down.')
        return

    async def handle_group_29_mod_channel_message(self, message):
        # If REVIEW_FLAG is true, then we are in review mode
        if REVIEW_FLAG == True:
            await self.moderator_flow(message)
        # typing review in the mod channel starts review mode
        elif message.content.lower() == "review":
            await self.review_messages(message)
        else:
            mod_channel = self.mod_channels[message.guild.id]
            await mod_channel.send("If you like to review reported messages please type \"review\".")

    def eval_text(self, message):
        '''
        Given a message, forwards the message to Perspective and returns a dictionary of scores.
        '''
        PERSPECTIVE_URL = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze'

        url = PERSPECTIVE_URL + '?key=' + self.perspective_key
        data_dict = {
            'comment': {'text': message.content},
            'languages': ['en'],
            'requestedAttributes': {
                'SEVERE_TOXICITY': {}, 'PROFANITY': {},
                'IDENTITY_ATTACK': {}, 'THREAT': {},
                'TOXICITY': {}, 'FLIRTATION': {}
            },
            'doNotStore': True
        }
        response = requests.post(url, data=json.dumps(data_dict))
        response_dict = response.json()

        scores = {}
        for attr in response_dict["attributeScores"]:
            scores[attr] = response_dict["attributeScores"][attr]["summaryScore"]["value"]

        return scores

    def code_format(self, text):
        return "```" + text + "```"

    async def review_messages(self, message):
        global REVIEW_FLAG
        mod_channel = self.mod_channels[message.guild.id]
        if review_queue.empty() == True:
            await mod_channel.send("There are currently no messages in the queue")
            return

        # Pop the first message off the queue and ask the moderator what they think about the message
        curr_message = review_queue.get()
        content = ""
        print(curr_message.attachments)
        if (len(curr_message.attachments) == 0):
            content = curr_message.content
        else:
            content = curr_message.attachments[0].url

        await mod_channel.send(f'According to company guidelines, should\n"{content}" by user "{curr_message.author.name}"\nbe taken down?\n(Answer with \"yes\" or \"no\" only)')
        REVIEW_FLAG = True

    async def moderator_flow(self, message):
        global REVIEW_FLAG
        mod_channel = self.mod_channels[message.guild.id]
        if message.content.lower() == "yes":
            await mod_channel.send(f'Message:\n"{message.content}" by user "{message.author.name}"\nThis message has been taken down.')
        # Case where the moderator doesn't type 'yes' or 'no'
        elif message.content.lower() != "no":
            await mod_channel.send('Please only answer with \"yes\" or \"no\"')
            return
        REVIEW_FLAG = False
        await mod_channel.send("You have just completed reviewing a message. If you would you like to review another message please type \"review\".")

    def automatic_flagging(self, scores):
        severe_toxicity = scores["SEVERE_TOXICITY"]
        profanity = scores["PROFANITY"]
        threat = scores["THREAT"]
        toxicity = scores["TOXICITY"]
        combined_score = severe_toxicity + profanity + threat + toxicity
        if combined_score > HARRASMENT_THRESHOLD:
            return True
        if severe_toxicity > MAX_SCORE or toxicity > MAX_SCORE or threat > MAX_SCORE:
            return True
        return False


client = ModBot(perspective_key)
client.run(discord_token)
