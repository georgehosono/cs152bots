from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_RECORDED = auto()
    REPORT_COMPLETE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    SPAM_KEYWORD = "spam"
    NOBLOCK_KEYWORD = "don't block"
    BLOCK_KEYWORD = "block"
    OFFENSE_KEYWORD = "offensive content"
    HARASSMENT_KEYWORD = "harassment"
    DANGER_KEYWORD = "imminent danger"
    SEXUAL_KEYWORD = "unwanted sexual content"
    PRIVATE_KEYWORD = "revealing private information"
    HATE_KEYWORD = "hate speech"
    THREAT_KEYWORD = "threats"
    NO_KEYWORD = "no"
    YES_KEYWORD = "yes"
    N_KEYWORD = "n"
    Y_KEYWORD = "y"
    LEGAL_KEYWORD = "take legal action"
    ABUSE_KEYWORD = "sexual abuse"
    HARM_KEYWORD = "self-harm"
    SUICIDAL_KEYWORD = "suicidal intent"
    VIOLENT_KEYWORD = "threat of violence"
    HARD_KEYWORD = "hard-block"
    SOFT_KEYWORD = "soft-block"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Please select the reason for reporting by entering a phrase that most matches the reason for reporting: 'spam', 'offensive content', 'harassment', or 'imminent danger'."]

        if message.content == self.SPAM_KEYWORD or message.content == self.OFFENSE_KEYWORD or message.content == self.SEXUAL_KEYWORD or message.content == self.PRIVATE_KEYWORD or message.content == self.HATE_KEYWORD or message.content == self.NO_KEYWORD:
            reply = "Thank you for reporting. Our content moderator team will review the message and decide on appropriate action. This may include post and/or account removal."
            reply += "Would you like to block the user? Please enter 'block' or 'don't block."
            self.state = State.REPORT_RECORDED
            return [reply]

        # if self.state == State.MESSAGE_IDENTIFIED:
        #     return ["<insert rest of reporting flow here>"]
        if message.content == self.HARASSMENT_KEYWORD:
            reply = "Please select type of harassment by entering one of the following: 'threats', 'unwanted sexual content', 'revealing private information', or 'hate speech'."
            return [reply]

        if message.content == self.DANGER_KEYWORD:
            reply = "Please select type of danger by entering one of the following: 'sexual abuse', 'self-harm', 'suicidal intent', or 'threat of violence'."
            return [reply]

        if message.content == self.THREAT_KEYWORD:
            reply = "Are you a victim of sexual abuse? Please type 'yes' or 'no'."
            return [reply]

        if message.content == self.YES_KEYWORD or message.content == self.ABUSE_KEYWORD:
            reply = "Does the content involve someone underage? Please type 'y' for yes and 'n' for no."
            return [reply]

        if message.content == self.Y_KEYWORD or message.content == self.N_KEYWORD:
            reply = "Would you like to potentially take legal action? Type 'take legal action' or 'no'."
            return [reply]


        if message.content == self.NOBLOCK_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Thank you for taking the time to complete this report."]

        if message.content == self.LEGAL_KEYWORD or message.content == self.HARM_KEYWORD or message.content == self.SUICIDAL_KEYWORD or message.content == self.VIOLENT_KEYWORD:
            reply = "Thank you for reporting. Our content moderator team will review the message and decide on appropriate action, including notifying the authorities if necessary. Our legal team may reach out for further question and next steps."
            reply += "Would you like to block the user? Please enter 'block' or 'don't block."
            return [reply]

        if message.content == self.BLOCK_KEYWORD:
            reply = "Please specify how you'd like to block the user by entering 'hard-block' or 'soft-block'."
            return [reply]

        if message.content == self.HARD_KEYWORD:
            reply = "You have chosen to hard-block the user. Thank you for taking the time to complete this report."
            return [reply]

        if message.content == self.SOFT_KEYWORD:
            reply = "You have chosen to soft-block the user. Thank you for taking the time to complete this report."
            return [reply]

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    


    

