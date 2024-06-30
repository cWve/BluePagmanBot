import time


def reply_with_slow_pyramid(self, message):
    if (message['source']['nick'] not in self.state or time.time() - self.state[message['source']['nick']] >
            self.cooldown):
        self.state[message['source']['nick']] = time.time()
        if len(message['command']['botCommandParams']) > 1 and message['command']['botCommandParams'][1].isnumeric():
            emote = message['command']['botCommandParams'][0]
            width = int(message['command']['botCommandParams'][1])
            if len(emote) * width + width - 1 < 500:
                text = ''
                for x in range(width):  # go up
                    text += (emote + ' ')
                    self.send_privmsg(message['command']['channel'], text)
                    time.sleep(1.6)
                for y in range(width-1):  # go down
                    text = text.rsplit(emote, 1)[0]
                    self.send_privmsg(message['command']['channel'], text)
                    time.sleep(1.6)
            else:
                text = 'Pyramid is too large to be displayed in chat. Use \
                a smaller pyramid width.'
                self.send_privmsg(message['command']['channel'], text)

        else:
            text = f"Width must be an integer. Usage: {self.command_prefix}pyramid {{name}} {{width}}"
            self.send_privmsg(message['command']['channel'], text)