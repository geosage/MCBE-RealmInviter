import asyncio
import discord
import os
from msal import PublicClientApplication
import sqlite3
from threading import Thread, Lock
from dotenv import load_dotenv
from tokenstuff import *
from realmchecking import *
import aiohttp
from datetime import datetime, timedelta 
import random
import math

# Extract the Xuids to invite from the txt
file_path = 'playerxuids.txt'
with open(file_path, 'r') as file:
    # Step 2: Initialize an empty list
    playerxuids = []

    # Step 3: Read each line and append its content to the list
    for line in file:
        playerxuids.append(line.strip())


random.shuffle(playerxuids)
#playerxuids = playerxuids[::1]

load_dotenv()

# Get the directory where the Python script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the relative path to the database file
db_file_path = os.path.join(script_dir, 'UserInfo.db')
# Connect to the SQLite database
conn = sqlite3.connect(db_file_path)
c = conn.cursor()


#Set currently inviting to false
c.execute("UPDATE invitetable SET currentlyinviting = 'False'")
conn.commit()


bot = discord.Bot()

logschannel = bot.get_partial_messageable(1113994131627323412)

embedthink = discord.Embed(
    title="",
    color=discord.Colour.orange(),
)
embedthink.add_field(
    name="The bot is processing your request. This may take up to 5 seconds...",
    value=""
)


# Dictionary to store ongoing link processes
ongoing_processes = {}


class LinkProcess:
    def __init__(self, ctx):
        self.ctx = ctx
        self.completed = True

    async def start(self):
        client_id = "" # Put urs here
        scopes = ["XboxLive.signin"]
        authority = "https://login.microsoftonline.com/consumers"
        pca = PublicClientApplication(client_id, authority=authority)

        flow = pca.initiate_device_flow(scopes)
        if "message" in flow:
            code = flow["user_code"]
            embed = discord.Embed(
                title="Link Your Microsoft Account.",
                color=discord.Colour.orange(),
            )
            embed.add_field(
                name=f"> Copy Your Code: {code}\n> Go to https://www.microsoft.com/link\n> Enter Your Unique Code\n> Sign In To Link Accounts",
                value=""
            )
            embed.set_footer(
                text="Shadow Realm Inviter",
                icon_url='https://cdn.discordapp.com/attachments/843951309253247026/1113236625095413842/72_x_72_3-Month_1.png'
            )
            embed.set_thumbnail(url="https://th.bing.com/th/id/OIP.QexRlFDy1uq4MOhrl819aQHaHa?pid=ImgDet&rs=1")

            await self.ctx.respond(embed=embed, ephemeral = True)
            await bot.wait_until_ready()

            embed = discord.Embed(
                title="Link Your Microsoft Account.",
                color=discord.Colour.orange(),
            )
            embed.add_field(name=f"Successfully linked your account!", value="")
            embed.set_footer(
                text="Shadow Realm Inviter",
                icon_url='https://cdn.discordapp.com/attachments/843951309253247026/1113236625095413842/72_x_72_3-Month_1.png'
            )

            result = await asyncio.to_thread(pca.acquire_token_by_device_flow, flow)
            await self.ctx.edit(embed=embed)

            access_token = result.get("access_token")
            refresh_token = result.get("refresh_token")
            user_id = self.ctx.author.id

            print(f"\nUser: {user_id}")
            print("Access Token:", access_token)
            print("Refresh Token:", refresh_token)
            xbl3token = getxbl3(access_token)
            print(xbl3token)
            
            # Store the variables in the database
            c.execute('''
                INSERT INTO link_data (user_id, access_token, refresh_token, xbl3token)
                VALUES (?, ?, ?, ?)
            ''', (user_id, access_token, refresh_token, xbl3token))  


            # Check if the user ID is already in the invites table
            c.execute("SELECT user_id FROM invitetable WHERE user_id = ?", (user_id,))
            result = c.fetchone()

            #Insert into the invite table if not already
            if result is None:
                c.execute('''
                    INSERT INTO invitetable (user_id, invites, invitesused, currentlyinviting, claimeddaily)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, 750, 0, 'False', 'False'))  

            print(f"\nSuccessfully added {user_id} to the databases.")
            await logschannel.send(f"{self.ctx.author} just linked their account!")
            conn.commit()

            self.completed = True
        else:
            print("An error occurred during the device code flow.")

        # Remove the process from the ongoing_processes dictionary
        del ongoing_processes[self.ctx.author.id]


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

    #Update the Invites Sent
    c.execute("SELECT invitesused FROM invitetable")
    total = sum(row[0] for row in c.fetchall())
    #Round to nearest 1000
    total = math.ceil(total / 1000)
    await bot.change_presence(activity=discord.Activity(name=f"{total}k Invites Sent", type=discord.ActivityType.watching))

    #Run the Daily Event
    await schedule_daily_event()


#Link --------------------------------------------------------------------------------------------------------------
@bot.slash_command(name="link", description="Link your account to the bot.")
async def link(ctx):
    print(f"{ctx.author.name} has just started a link process!")

    # Check if the user is already in the database
    c.execute("SELECT user_id FROM link_data WHERE user_id = ?", (int(ctx.author.id),))
    result = c.fetchone()

    if result is not None:
        await ctx.respond("Your account is already linked.", ephemeral=True)
        return

    if ctx.author.id in ongoing_processes:
        await ctx.respond("A link process is already running. Please wait until it finishes.", ephemeral=True)
        return

    process = LinkProcess(ctx)
    ongoing_processes[ctx.author.id] = process

    try:
        await process.start()
    except Exception as e:
        print(f"An error occurred during the link process: {e}")
        del ongoing_processes[ctx.author.id]

#UnLink --------------------------------------------------------------------------------------------------------
@bot.slash_command(name="unlink", description="Remove your account from our database.")
async def unlink(ctx):
    user_id = str(ctx.author.id)  # Retrieve the user ID as a string

    # Check if the user ID is already in the database
    c.execute("SELECT user_id FROM link_data WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if result is not None:
        # User ID is already linked, remove the record from the database
        c.execute("DELETE FROM link_data WHERE user_id = ?", (user_id,))
        conn.commit()  # Commit the changes

        await logschannel.send(f"{ctx.author} just unlinked their account!")
        await ctx.respond("Your account has been unlinked.", ephemeral=True)
    else:
        await ctx.respond("Your account is not linked. Type /link to do so.", ephemeral=True)

#Query ---------------------------------------------------------------------------------------------------------------------
@bot.slash_command(name="queryinvites", description="Check your invite stats")
async def queryinvites(ctx):
    user = ctx.author


    # Check if the user ID is already in the database
    c.execute("SELECT user_id FROM link_data WHERE user_id = ?", (user.id,))
    result = c.fetchone()


    if result is not None:
        # Get the number of invites the user has
        c.execute("SELECT invites, invitesused FROM invitetable WHERE user_id = ?", (user.id,))
        result = c.fetchone()
        invites = result[0]
        invites_used = result[1]

        embed = discord.Embed(
        title=f"{user.name}'s Invite Statistics",
        color=discord.Colour.orange(),
        )
        embed.add_field(
            name=f"> Invites To Send - `{invites}`\n> Invites Sent - `{invites_used}`",
            value=""
        )
        embed.set_footer(
            text="Shadow Realm Inviter",
            icon_url='https://cdn.discordapp.com/attachments/843951309253247026/1113236625095413842/72_x_72_3-Month_1.png'
        )

        await ctx.respond(embed=embed)
    else:
        await ctx.respond("You have not linked your account. Type /link to do so.", ephemeral=True)



#AddInvites ----------------------------------------------------------------------------------------------------------------
@bot.slash_command(name="updateinvites", description="Give a User Invites")
async def updateinvites(ctx, user: discord.Member, invitestoadd: int):
    sender = ctx.author.id
    user_id = user.id

    if sender == 614570887160791050:
        # Check if the user ID is already in the database
        c.execute("SELECT user_id FROM link_data WHERE user_id = ?", (user_id,))
        result = c.fetchone()

        if result is not None:
            # Get the number of invites the user has
            c.execute("SELECT invites FROM invitetable WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            current_invites = result[0]

            final_invites = current_invites + invitestoadd

            c.execute("UPDATE invitetable SET invites = ? WHERE user_id = ?", (final_invites, user_id))
            await ctx.respond(f"{user.name} now has {final_invites} invites!")
            await logschannel.send(f"{ctx.author} just gave {user.name}, {invitestoadd} invites!")
            conn.commit()
        else:
            await ctx.respond("The user has not linked their account", ephemeral=True)

    else:
        await ctx.respond("You do not have permission to run this command!", ephemeral=True)



#SendInvites ------------------------------------------------------------------------------------------------------------------------------------------
async def send_request(self, invitedplayerxuid, counter):
    url = f'https://pocket.realms.minecraft.net/invites/{self.realmid}/invite/update'
    headers = {
        'Accept': '*/*',
        'authorization': f'{self.xbltoken}',
        'client-version': '1.17.10',
        'user-agent': 'MCPE/UWP',
        'Accept-Language': 'en-GB,en',
        'Accept-Encoding': 'gzip, deflate, be',
        'Host': 'pocket.realms.minecraft.net'
    }

    data = {
        "invites": {
            invitedplayerxuid: "ADD"  # or "REMOVE"
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=data) as response:
                if response.status == 200:
                    print(f"Request successful for {self.realmname} to PLAYER_XUID: {invitedplayerxuid}")
                    print(f"{counter} Invites Sent!")


                else:
                    print(f"Request failed with status code {response.status} for PLAYER_XUID: {invitedplayerxuid}")
    except aiohttp.ClientError as e:
        print(f"An error occurred for PLAYER_XUID: {invitedplayerxuid}. Error: {str(e)}")


#Build Invite Class
class CodeRunner:
    def __init__(self, ctx, invitestosend, invitesused, realmid, realmname, xbltoken):
        self.ctx = ctx
        self.invitestosend = invitestosend
        self.invitesused = invitesused
        self.realmid = realmid
        self.realmname = realmname
        self.xbltoken = xbltoken
        self.playerxuids = playerxuids
        self.randomnum = 0
        self.tasks = []
        self.counting = 0
        
        self.embedinvited = discord.Embed(
            title="",
            color=discord.Colour.orange(),
        )

    async def run_code_block(self):
        print(self.invitesused)

        #Build and send embed to start inviting
        embedinvited = discord.Embed(
            title="",
            color=discord.Colour.orange(),
        )
        embedinvited.add_field(
            name=f"Successfully started inviting {self.invitestosend} members to {self.realmname}. You will be notified once it has been completed.",
            value=""
        )
        await self.ctx.edit(embed=embedinvited)

        #Make embed to send in public channel
        embedlogs = discord.Embed(
            title="",
            color=discord.Colour.orange(),
        )
        embedlogs.add_field(
            name=f"{self.ctx.author} just sent {self.invitestosend} invites for their realm!",
            value=""
        )
        publiclogschannel = bot.get_channel(1115032600705241239)
        await publiclogschannel.send(embed=embedlogs)

        for i in range(self.invitesused, self.invitesused + self.invitestosend + 1): # Ik ur reading this vision...
            self.counting += 1
            player_xuid = playerxuids[i]
            #Thing Runs Here

            task = asyncio.create_task(send_request(self, player_xuid, self.counting))
            self.tasks.append(task)
            # Basically stops them getting banned v v v
            await asyncio.sleep(random.uniform(2, 2.8))
            self.randomnum = random.randint(1, 100)
            if self.randomnum >= 95:
                await asyncio.sleep(random.randint(5, 10))

        #Embed to DM when finished.
        embedfinished = discord.Embed(
            title="",
            color=discord.Colour.orange(),
        )
        embedfinished.add_field(
            name=f"{self.invitestosend} invites have been successfully sent for {self.realmname}. To check how many invites you have type /queryinvites",
            value=""
        )
        await self.ctx.author.send(embed=embedfinished)


        c.execute("UPDATE invitetable SET currentlyinviting = 'False' WHERE user_id = ?", (self.ctx.author.id,))
        conn.commit()
        await asyncio.gather(*self.tasks)



@bot.slash_command(name="sendinvites", description="Invite Users To Your Realm")
async def sendinvites(ctx, realmcode: str, invitestosend: int):
    user = ctx.author
    user_id = user.id

    # Check if the user ID is already in the database
    c.execute("SELECT user_id FROM 'link_data' WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if result is not None:
        # Get the number of invites the user has
        c.execute("SELECT invites, invitesused FROM invitetable WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        invites = result[0]
        invitesused = result[1]

        if invites <= 0:
            channel = bot.get_channel(1113141056167485487)
            await ctx.respond(f"You do not have any more invites avalible. Please go to {channel.mention} to purchase/gain more invites. https://discord.gg/tqXp4qysxy", ephemeral=True)
        else:
            if invitestosend > invites:
                channel = bot.get_channel(1113141056167485487)
                await ctx.respond(f"You do not have enough invites to complete this request. Please go to {channel.mention} to purchase/gain more invites or lower the amount you wish to send. https://discord.gg/tqXp4qysxy", ephemeral=True)
            else:
                c.execute("SELECT currentlyinviting FROM 'invitetable' WHERE user_id = ?", (user_id,))
                result = c.fetchone()
                result = result[0]
                
                if result == 'True':
                    await ctx.respond(f"You are already sending invites to a realm. You will be notified once this has been completed.", ephemeral=True)
                else:
                    await ctx.respond(embed=embedthink)
                    refreshtoken(user_id, conn, c)
                    #Get Xbl3Token from the database
                    c.execute("SELECT xbl3token FROM link_data WHERE user_id = ?", (user_id,))
                    result = c.fetchone()
                    xbl3token = result[0]

                    #Get the realm information
                    realminfo = getinfofromcode(realmcode, xbl3token)
                    if realminfo != False:
                        realmid = realminfo['id']
                        #Check if the user is the realm owner
                        isowner = checkowner(realmid, xbl3token)
                        if isowner != False:
                            realmname = realminfo['name']
                            c.execute("UPDATE invitetable SET invites = ? WHERE user_id = ?", (invites-invitestosend, user_id))
                            conn.commit()
                            c.execute("UPDATE invitetable SET invitesused = ? WHERE user_id = ?", (invitesused+invitestosend, user_id))
                            conn.commit()
                            await logschannel.send(f"{ctx.author} just sent {invitestosend} invites to {realmname}.")

                            c.execute("UPDATE invitetable SET currentlyinviting = 'True' WHERE user_id = ?", (user_id,))
                            conn.commit()
                            # Create an instance of CodeRunner for the user
                            runner = CodeRunner(ctx, invitestosend, invitesused, realmid, realmname, xbl3token)

                            # Create a task for the user to run the code block
                            task = asyncio.create_task(runner.run_code_block())

                            # Wait for the task to complete
                            await task
                        else:
                            embednotowner = discord.Embed(
                                title="",
                                color=discord.Colour.orange(),
                            )
                            embednotowner.add_field(
                                name=f"You are not the owner of {realminfo['name']}",
                                value=""
                            )    
                            await ctx.edit(embed=embednotowner)

                    else: #Invalid Realm Code Entered
                        embedcode = discord.Embed(
                            title="",
                            color=discord.Colour.orange(),
                        )
                        embedcode.add_field(
                            name=f"{realmcode} is not a valid realm code.",
                            value=""
                        )
                        await ctx.edit(embed=embedcode)
    else:
        await ctx.respond("You have not linked your account. Type /link to do so.", ephemeral=True)


#Claim Daily Invites ---------------------------------------------------------------------------------------------------------------------
@bot.slash_command(name="claimdaily", description="Claim your daily invites!")
async def queryinvites(ctx):
    user = ctx.author

    # Check if the user ID is already in the database
    c.execute("SELECT user_id FROM link_data WHERE user_id = ?", (user.id,))
    result = c.fetchone()

    if result is not None:
        # Check if they have already claimed
        c.execute("SELECT claimeddaily FROM invitetable WHERE user_id = ?", (user.id,))
        result = c.fetchone()[0]
        
        # Check if false and wtv
        if result == 'False':
            c.execute("UPDATE invitetable SET invites = invites + 250 WHERE user_id = ?", (user.id,))
            c.execute("UPDATE invitetable SET claimeddaily = 'True' WHERE user_id = ?", (user.id,))
            conn.commit()

            embedclaimed = discord.Embed(
                title="",
                color=discord.Colour.orange(),
            )
            embedclaimed.add_field(
                name=f"You have successfully claimed your daily invites. Type /queryinvites to find out how many you have.",
                value=""
            )

            await ctx.respond(embed=embedclaimed)
        else:
            channel = bot.get_channel(1113141056167485487)
            await ctx.respond(f"You have already claimed your free daily invites today. Go to {channel.mention} to find out how to get more!", ephemeral=True)

    else:
        await ctx.respond("You have not linked your account. Type /link to do so.", ephemeral=True)


#Give free invites once a day -----------------------------------------------------------------------------------------------------------------------------------
async def schedule_daily_event():
    now = datetime.now()
    target_time = datetime.combine(datetime.now().date(), datetime.now().time().replace(hour=21, minute=15))  # Set the desired time here
    if now > target_time:
        target_time += timedelta(days=1)  # If the target time has already passed today, schedule it for the next day
    time_until_event = (target_time - now).total_seconds()
    print(f"Daily event starts in {time_until_event} seconds")
    await asyncio.sleep(time_until_event)
    await daily_event()

async def daily_event():
    c.execute("UPDATE invitetable SET claimeddaily = 'False'")
    conn.commit()

    #Build the embed to send
    channeltag = bot.get_channel(1113141056167485487)
    embeddaily = discord.Embed(
        title="",
        color=discord.Colour.orange(),
    )
    embeddaily.add_field(
        name=f"Everyone can now claim their free 250 daily invites. Type /claimdaily to claim yours. Go to {channeltag.mention} to find out how to get more invites!",
        value=""
    )

    print("Just sent out the daily 250 invites.")
    publiclogschannel = bot.get_channel(1115032600705241239)
    await publiclogschannel.send(embed=embeddaily)


# Run the bot from the token in ".env"
bot.run(os.getenv('TOKEN'))

