import discord
from discord.ext import commands
import os
import re

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    pattern = re.compile(r'\b[a-zA-Z]{3}-\d{3}\b')
    rekkari = pattern.search(message.content)

    if rekkari!=None:
        await message.channel.send(rekkari.group())

    await bot.process_commands(message)


    
bot.run("NzMwMDM4ODY0Mjc3NjY4MDAz.GT3CVi.UFxvR_WRU9Fb8r8TO9L1ks7vGbD0WLvpX_0Jys")