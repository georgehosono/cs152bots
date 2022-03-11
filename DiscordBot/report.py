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
    SPAM_KEYWORD = "1"
    NOBLOCK_KEYWORD = "6"
    BLOCK_KEYWORD = "5"
    OFFENSE_KEYWORD = "2"
    HARASSMENT_KEYWORD = "3"
    DANGER_KEYWORD = "4"
    SEXUAL_KEYWORD = "8"
    PRIVATE_KEYWORD = "9"
    HATE_KEYWORD = "10"
    THREAT_KEYWORD = "7"
    NO_KEYWORD = "no"
    YES_KEYWORD = "yes"
    N_KEYWORD = "n"
    Y_KEYWORD = "y"
    LEGAL_KEYWORD = "15"
    ABUSE_KEYWORD = "11"
    HARM_KEYWORD = "12"
    SUICIDAL_KEYWORD = "13"
    VIOLENT_KEYWORD = "14"
    HARD_KEYWORD = "16"
    SOFT_KEYWORD = "17"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
    
        self.old_message = None

    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        final_message = self.old_message
        print("Final message is: ", final_message)
        if final_message is None:
            final_message = message

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return [("Report cancelled.", final_message)]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [(reply, final_message)]
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return [(["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."], final_message)]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return [(["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."], final_message)]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return [(["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."], final_message)]
            try:
                message = await channel.fetch_message(int(m.group(3)))
                self.old_message = message
                q = message
            except discord.errors.NotFound:
                return [(["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."], final_message)]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
            return [(["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Please select the reason for reporting by entering a number that most matches the reason for reporting: 1. spam, 2. offensive content, 3. harassment, or 4. imminent danger. Please enter 1, 2, 3, or 4."], final_message)]

        if message.content == self.SPAM_KEYWORD or message.content == self.OFFENSE_KEYWORD or message.content == self.SEXUAL_KEYWORD or message.content == self.PRIVATE_KEYWORD or message.content == self.HATE_KEYWORD or message.content == self.NO_KEYWORD:
            reply = "Thank you for reporting. Our content moderator team will review the message and decide on appropriate action. This may include post and/or account removal. "
            reply += "Would you like to block the user? Please choose from options: 5. block or 6. don't block. Please enter 5 or 6."
            self.state = State.REPORT_RECORDED
            return [(reply, final_message)]

        # if self.state == State.MESSAGE_IDENTIFIED:
        #     return ["<insert rest of reporting flow here>"]
        if message.content == self.HARASSMENT_KEYWORD:
            reply = "Please select type of harassment by entering a number that most matches the reason for reporting: 7. threats, 8. unwanted sexual content, 9. revealing private information, or 10. hate speech. Please enter 7, 8, 9, or 10."
            return [(reply, final_message)]

        if message.content == self.DANGER_KEYWORD:
            reply = "Please select type of danger by entering a number that most matches the reason for reporting: 11. sexual abuse, 12. self-harm, 13. suicidal intent, or 14. threat of violence. Please enter 11, 12, 13, or 14."
            return [(reply, final_message)]

        if message.content == self.THREAT_KEYWORD:
            reply = "Are you a victim of sexual abuse? Please type 'yes' or 'no'."
            return [(reply, final_message)]

        if message.content == self.YES_KEYWORD or message.content == self.ABUSE_KEYWORD:
            reply = "Does the content involve someone underage? Please type 'y' for yes and 'n' for no."
            return [(reply, final_message)]

        if message.content == self.Y_KEYWORD or message.content == self.N_KEYWORD:
            reply = "Would you like to potentially take legal action? Please enter a phrase that most matches that action you'd like to take: 15. take legal action or no. don't take legal action. Please enter 15 or no."
            return [(reply, final_message)]


        if message.content == self.NOBLOCK_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return [("Thank you for taking the time to complete this report.", final_message)]

        if message.content == self.LEGAL_KEYWORD or message.content == self.HARM_KEYWORD or message.content == self.SUICIDAL_KEYWORD or message.content == self.VIOLENT_KEYWORD:
            reply = "Thank you for reporting. Our content moderator team will review the message and decide on appropriate action, including notifying the authorities if necessary. Our legal team may reach out for further question and next steps."
            reply += "Would you like to block the user? Please choose from options: 5. block or 6. don't block. Please enter 5 or 6."
            return [(reply, final_message)]

        if message.content == self.BLOCK_KEYWORD:
            reply = "Please specify how you'd like to block the user by choosing from the following: 16. hard-block or 17. soft-block. Please enter 16 or 17."
            return [(reply, final_message)]

        if message.content == self.HARD_KEYWORD:
            self.state = State.REPORT_COMPLETE
            reply = "You have chosen to hard-block the user. Thank you for taking the time to complete this report."
            return [(reply, final_message)]

        if message.content == self.SOFT_KEYWORD:
            self.state = State.REPORT_COMPLETE
            reply = "You have chosen to soft-block the user. Thank you for taking the time to complete this report."
            return [(reply, final_message)]

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    


    

