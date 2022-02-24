# bot.py
from collections import deque
from email.message import Message
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from unidecode import unidecode
from report import Report
from collections import deque

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
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
    claim_buster_key = tokens['claim_buster']

def fact_check(input_claim):
    input_claim = "Joe Biden has visited Delaware 25 times since becoming president."

    # Define the endpoint (url) with the claim formatted as part of it, api-key (api-key is sent as an extra header)
    api_endpoint = f"https://idir.uta.edu/claimbuster/api/v2/query/fact_matcher/{input_claim}"
    request_headers = {"x-api-key": claim_buster_key}

    # Send the GET request to the API and store the api response
    api_response = requests.get(url=api_endpoint, headers=request_headers)

    # Print out the JSON payload the API sent back
    # print(api_response.json()["justification"][0]["truth_rating"])

class ModBot(discord.Client):
    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.perspective_key = key
        # ****
        self.curr_message = discord.Message     # most recent message mods are looking at
        self.messages_queue = deque()
        self.points = {} # map from user IDs to points (more points = more reports on their messages)

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
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

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
        # # Ignore messages from the bot 
        # if message.author.id == self.user.id:
        #     return

        # Check if this message was sent in a server ("guild") or if it's a DM
        message.content = unidecode(message.content)
        if message.guild:
            await self.handle_channel_message(message)
        else:
            # here
            await self.handle_dm(message)

    async def on_message_edit(self, before, after):
        '''
        This function is called whenever a message is edited
        '''
        await self.handle_channel_message(after)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
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
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):    # CHANGED THIS FUNCTION
        # Only handle messages sent in the "group-#" channel xxxx
        mod_channel = self.mod_channels[message.guild.id]
        if message.channel.name == f'group-{self.group_num}':
            # Forward the message to the mod channel
            self.curr_message = message
            self.messages_queue.append(message)
            await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')

            scores = self.eval_text(message)
            await mod_channel.send(self.code_format(json.dumps(scores, indent=2)))
        elif message.channel.name == f'group-{self.group_num}-mod':
            if 'Forwarded message' in message.content:
                # text = message.content[message.content.find('\"'):]
                question = await mod_channel.send(f'Does the above message fall into any of the following categories? \n 🔴 Harassment/Bullying \n 🟠 False or Misleading Information \n 🟡 Violence/Graphic Imagery \n 🟢 Spam \n 🔵 Other Harmful Content \n')
                await question.add_reaction('🔴') 
                await question.add_reaction('🟠') 
                await question.add_reaction('🟡') 
                await question.add_reaction('🟢') 
                await question.add_reaction('🔵') 
                
            # return

        else:
            return

        # # Only handle messages sent in the "group-#" channel
        # if not message.channel.name == f'group-{self.group_num}':
        #     return

        # # Forward the message to the mod channel
        # mod_channel = self.mod_channels[message.guild.id]
        # await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')

        # scores = self.eval_text(message)
        # await mod_channel.send(self.code_format(json.dumps(scores, indent=2)))

    async def on_raw_reaction_add(self, payload):
        channel = await self.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        # user_id = await self.fetch_user(payload.user_id)
        emoji = payload.emoji
    
        # if len(self.messages_queue) > 0:
        
        # self.messages_queue.popleft()

        mod_channel = self.mod_channels[self.curr_message.guild.id]
        # mod_channel = self.mod_channels[curr_message_obj.guild.id]
        if (channel == mod_channel) and payload.user_id != self.user.id:
            curr_message_obj = self.messages_queue[0]
            curr_message = curr_message_obj.content
            author_id = curr_message_obj.author.id
            if str(emoji) == str('🔴'):
                # await self.curr_message.add_reaction('🔴')
                await curr_message_obj.add_reaction('🔴')
                await mod_channel.send('Thank you! We have tagged this message and will inform the Hate & Harassment Team.')
                self.messages_queue.popleft()
            if str(emoji) == str('🟠'):
                # await self.curr_message.add_reaction('🟠')
                await curr_message_obj.add_reaction('🟠')
                question1 = await mod_channel.send(f'Does the message "{curr_message}" contain false or misleading information? \n ✅ Yes \n ❌ No')
                await question1.add_reaction('✅') 
                await question1.add_reaction('❌')
            if str(emoji) == str('🟡'):
                # await self.curr_message.add_reaction('🟡')
                await curr_message_obj.add_reaction('🟡')
                await mod_channel.send('Thank you! We have tagged this message and will will inform the Violence/Graphic Imagery Team.')
                self.messages_queue.popleft()
            if str(emoji) == str('🟢'):
                # await self.curr_message.add_reaction('🟢')
                await curr_message_obj.add_reaction('🟢')
                await mod_channel.send('Thank you! We have tagged this message and will will inform the Spam Team.')
                self.messages_queue.popleft()
            if str(emoji) == str('🔵'):
                # await self.curr_message.add_reaction('🔵')
                await curr_message_obj.add_reaction('🔵')
                await mod_channel.send('Thank you! We have tagged this message and will will inform the Multidisciplinary Team.')
                self.messages_queue.popleft()
            if str(emoji) == str('✅'):
                question2 = await mod_channel.send(f'Is the message "{curr_message}": \n ⬅️ Fabricated Content / Disinformation, or \n ➡️ Satire / Parody')
                await question2.add_reaction('⬅️')
                await question2.add_reaction('➡️')
            if str(emoji) == str('❌'):
                await mod_channel.send('Thank you!')
                self.messages_queue.popleft()
            if str(emoji) == str('⬅️'):
                question3 = await mod_channel.send(f'Please rate the harm of the message "{curr_message}": \n 1️⃣ (Immediate Harm) \n 2️⃣ (Moderate Harm) \n 3️⃣ (Low Harm)')
                await question3.add_reaction('1️⃣') 
                await question3.add_reaction('2️⃣')
                await question3.add_reaction('3️⃣')
            if str(emoji) == str('➡️'):
                await mod_channel.send('Thank you! We will take action if the issue becomes more serious.')
                self.messages_queue.popleft()
            THRESHOLD_POINTS = 50
            if str(emoji) == str('1️⃣'):
                # await mod_channel.send(f'message: "{self.curr_message.content}"')
                # await self.curr_message.delete()
                await curr_message_obj.delete()
                await mod_channel.send('Thank you! We have taken down the message.')
                self.points[author_id] = self.points.get(author_id, 0) + 8
                self.messages_queue.popleft()
            if str(emoji) == str('2️⃣'):
                # await self.curr_message.add_reaction('🚩')
                await curr_message_obj.add_reaction('🚩')
                await mod_channel.send('Thank you! We have flagged the message.')
                self.points[author_id] = self.points.get(author_id, 0) + 5
                self.messages_queue.popleft()
            if str(emoji) == str('3️⃣'):
                await mod_channel.send('Thank you! We will take action if the issue becomes more serious.')
                self.points[author_id] = self.points.get(author_id, 0) + 2
                self.messages_queue.popleft()
            if self.points.get(author_id, 0) > THRESHOLD_POINTS:
                await mod_channel.send('The author of the message has been banned because they have exceeded the threshold of allowed points for reports against them.')

        # await channel.send("Hello")

        msg_validity = fact_check(message.content)
        if msg_validity != "" and msg_validity != "True" and msg_validity != None:
            await mod_channel.send(f'This message has been fact checked as being potentially false')

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


client = ModBot(perspective_key)
client.run(discord_token)