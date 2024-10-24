import random
import time
from threading import Timer
from Commands import gemini, describe, ascii
from vertexai.generative_models import Part


def reply_with_guess(self, message):
    if (message['source']['nick'] not in self.state or time.time() - self.state[message['source']['nick']] > 0.4):
        self.state[message['source']['nick']] = time.time()
        channel_id = message["tags"]["room-id"]

        if not self.guessGameActive:
            # Start the game
            self.guessGameActive = True
            self.numRounds = 5
            is_global = False

            # Check if the user wants global emotes or number to specify rounds (1 - 4)
            if message['command']['botCommandParams']:
                params = message['command']['botCommandParams']
                if "global" in params:
                    is_global = True
                
                if params.isdigit() and int(params) < 5 and int(params) > 0:
                    self.numRounds = int(params)

            # Fetch emotes (either from channel or globally)
            emotes_list = get_random_emotes(
                self, channel_id, self.numRounds, is_global)

            if not emotes_list:
                self.send_privmsg(message['command']
                                  ['channel'], "No emotes found!")
                self.guessGameActive = False
                return

            if len(emotes_list) < self.numRounds:
                self.numRounds = len(emotes_list)
            mode = "Global Emotes" if is_global else "Channel Emotes"

            self.send_privmsg(
                message['command']['channel'], f"Game started! Mode is {mode}")
            self.gameEmotes = emotes_list
            # start a timer for 40s, if no one guesses emote in time, then reveal the emote.
            currentEmote = self.gameEmotes[self.currentRound]
            print(self.gameEmotes)
            start_new_round(self, message['command']['channel'])

        # users will guess emotes using <guess EMOTE_NAME
        if not message['command']['botCommandParams']:
            return
        guess = message['command']['botCommandParams']

        currentEmote = self.gameEmotes[self.currentRound]
        if guess == currentEmote:
            # stop the timer
            self.guessGameRoundTimer.cancel()
            if self.hintTimer:
                self.hintTimer.cancel()

            # user guessed emote right, move to next round
            self.send_privmsg(
                message['command']['channel'], f"{message['tags']['display-name']} guessed it right! It's {currentEmote}")

            time.sleep(1.1)
            if self.currentRound + 1 == self.numRounds:
                # end the game
                self.send_privmsg(
                    message['command']['channel'], "Game has ended.")
                reset_game(self)
                return
            self.currentRound += 1
            start_new_round(self, message['command']['channel'])


def start_new_round(self, channel):
    currentEmote = self.gameEmotes[self.currentRound]
    emote_url = self.db['Emotes'].find_one({"name": currentEmote})["url"]
    
    if not emote_url:
        self.send_privmsg(
            channel, "Emote was not found in database! Moving on to next round...")
        if self.guessGameRoundTimer:
            self.guessGameRoundTimer.cancel()
        if self.hintTimer:
            self.hintTimer.cancel()
        # Increment here only if the emote is not found, to avoid skipping the round
        self.currentRound += 1
        start_new_round(self, channel)
        return

    content_type = describe.get_content_type(emote_url)
    descr = "Give a description for this emote in 2 sentences. Start with 'This emote'"
    try:
        image = Part.from_uri(
            mime_type=content_type,
            uri=emote_url
        )
        description = gemini.generate_emote_description([image, descr])
    except Exception as e:
        print(e)
        self.send_privmsg(channel, str(e)[0:400])
        time.sleep(0.5)
        self.send_privmsg(
            channel, "Emote was not found in database! Moving on to next round...")
        if self.guessGameRoundTimer:
            self.guessGameRoundTimer.cancel()
        if self.hintTimer:
            self.hintTimer.cancel()
        self.currentRound += 1
        start_new_round(self, channel)
        return

    if not description:
        self.send_privmsg(
            channel, "Emote description could not be generated. Moving on to next round...")
        if self.guessGameRoundTimer:
            self.guessGameRoundTimer.cancel()
        if self.hintTimer:
            self.hintTimer.cancel()
        self.currentRound += 1
        start_new_round(self, channel)
        return

    self.send_privmsg(
        channel, f"Round {self.currentRound + 1}: {description} Guess the emote!")  # Display round as 1-based

    # Start the 40-second timer for this round
    self.guessGameRoundTimer = Timer(
        40, reveal_emote, (self, channel, currentEmote))
    self.guessGameRoundTimer.start()

    # Start the hint timer after 20 seconds
    self.hintTimer = Timer(
        20, provide_hint, (self, channel, emote_url))
    self.hintTimer.start()


def provide_hint(self, channel, emote_url):
    # Provide a hint from ascii
    hint = ascii.first_frame(channel, emote_url)
    self.send_privmsg(channel, hint)


def reveal_emote(self, channel, emote):
    self.send_privmsg(
        channel, f"The emote was {emote} Disappointing performance :Z")

    if self.currentRound + 1 == self.numRounds:
        # End the game if all rounds are done
        self.send_privmsg(
            channel, "Game has ended.")
        reset_game(self)
    else:
        # Start the next round
        time.sleep(1.1)
        self.currentRound += 1
        start_new_round(self, channel)


def get_current_emote(self):
    if self.guessGameActive and self.gameEmotes:
        return self.gameEmotes[self.currentRound]


def reset_game(self):
    self.guessGameActive = False
    self.currentRound = 0
    self.gameEmotes = []
    self.numRounds = 5
    self.guessGameRoundTimer = None
    self.hintTimer = None
    return


def get_random_emotes(self, channel_id, num_emotes=5, is_global=False):
    if is_global:
        # Fetch global Twitch emotes
        global_emote_records = self.db['Emotes'].find({"emote_type": "Twitch"})
        global_emotes = [emote['name'] for emote in global_emote_records]

        # If fewer emotes found, return all available
        if len(global_emotes) <= num_emotes:
            return global_emotes

        # Return a random sample of global emotes
        return random.sample(global_emotes, num_emotes)

    # Fetch emote IDs from the ChannelEmotes collection
    emote_records = self.db['ChannelEmotes'].find(
        {"channel_id": channel_id}, {"emote_id": 1})
    emote_ids = [record['emote_id'] for record in emote_records]

    if not emote_ids:
        return []

    # Select random emote_ids (limit the number of emotes if needed)
    random_emote_ids = random.sample(
        emote_ids, min(num_emotes, len(emote_ids)))

    # Fetch emote names using the $in operator in one query
    emote_records = self.db['Emotes'].find(
        {"emote_id": {"$in": random_emote_ids}}, {"name": 1})

    # Collect the names from the query result
    emote_names = [emote['name'] for emote in emote_records]

    # If no names found, return an empty list
    if not emote_names:
        return []

    return emote_names
