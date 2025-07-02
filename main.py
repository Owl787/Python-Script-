import os
import discord
from discord.ext import commands
import asyncio
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))
CONTROL_CHANNEL_ID = int(os.getenv("CONTROL_CHANNEL_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", self_bot=True, intents=intents)

# Store reactions per message
message_reactions = defaultdict(dict)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

@bot.event
async def on_reaction_add(reaction, user):
    if user.id == bot.user.id:
        return

    msg = reaction.message
    if msg.channel.id == TARGET_CHANNEL_ID:
        message_reactions[msg.id][user.id] = str(reaction.emoji)

@bot.command()
async def check(ctx, message_id: int):
    """Check reactions on a message and write P commands."""
    if ctx.channel.id != CONTROL_CHANNEL_ID:
        return

    try:
        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        message = await target_channel.fetch_message(message_id)

        users_handled = set()

        for reaction in message.reactions:
            async for user in reaction.users():
                if user.id == bot.user.id:
                    continue

                # Write #P <user_id>
                if user.id not in users_handled:
                    p_msg = await ctx.send(f"#P {user.id}")
                    await p_msg.add_reaction("❌")
                    users_handled.add(user.id)
                    await asyncio.sleep(0.5)

                # Write #P for the message author if they’re not the same
                if message.author.id != user.id and message.author.id not in users_handled:
                    p_msg = await ctx.send(f"#P {message.author.id}")
                    await p_msg.add_reaction("❌")
                    users_handled.add(message.author.id)
                    await asyncio.sleep(0.5)

        # Track reactions for possible removal
        for reaction in message.reactions:
            async for user in reaction.users():
                if user.id != bot.user.id:
                    message_reactions[message.id][user.id] = str(reaction.emoji)

    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.event
async def on_raw_reaction_add(payload):
    """When we react with ❌ to a #P message, remove the original user's reaction."""
    if payload.user_id != bot.user.id:
        return
    if str(payload.emoji.name) != "❌":
        return

    channel = bot.get_channel(payload.channel_id)
    if channel.id != CONTROL_CHANNEL_ID:
        return

    try:
        msg = await channel.fetch_message(payload.message_id)
        if not msg.content.startswith("#P "):
            return

        user_id = int(msg.content.split()[1])

        for message_id, reactions in list(message_reactions.items()):
            if user_id in reactions:
                emoji = reactions[user_id]
                target_channel = bot.get_channel(TARGET_CHANNEL_ID)
                target_msg = await target_channel.fetch_message(message_id)
                await target_msg.remove_reaction(emoji, discord.Object(id=user_id))
                print(f"Removed {emoji} from user {user_id} on message {message_id}")
                del reactions[user_id]
                break

    except Exception as e:
        print(f"Failed to remove reaction: {e}")

bot.run(TOKEN)
