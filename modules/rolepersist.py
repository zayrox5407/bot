"""
MIT License
Copyright (c) 2020 GamingGeek

Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


from discord.ext import command
from fire.converters import Role
import traceback
import datetime
import discord


class RolePersist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_persists = {}
        self.bot.loop.create_task(self.load_role_persists())

    async def load_role_persists(self):
        await self.bot.wait_until_ready()
        q = 'SELECT * FROM rolepersists;'
        rolepersists = await self.bot.db.fetch(q)
        for rp in rolepersists:
            if rp['gid'] not in self.bot.premium_guilds:
                continue
            if rp['gid'] not in self.role_persists:
                self.role_persists[rp['gid']] = {}
            self.role_persists[rp['gid']][rp['uid']] = rp['roles']
        self.bot.logger.info('$GREENLoaded persisted roles!')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if guild.id not in self.role_persists:
            return
        if member.id not in self.role_persists[guild.id]:
            return
        persisted = [
            guild.get_role(r) for r in self.role_persists[guild.id][member.id] if guild.get_role(r)
        ]
        if persisted:
            try:
                await member.add_roles(*persisted, reason=f'Persisted Roles', atomic=False)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.guild.id not in self.role_persists:
            return
        if after.id not in self.role_persists[after.guild.id]:
            return
        if before.roles != after.roles:
            broles = []
            aroles = []
            for role in before.roles:
                broles.append(role)
            for role in after.roles:
                aroles.append(role)
            s = set(aroles)
            removed = [x for x in broles if x not in s]
            if len(removed) >= 1:
                roleids = [r.id for r in removed]
                current = [r for r in self.role_persists[after.guild.id][after.id]]
                for rid in roleids:
                    if rid not in current:
                        current.append(rid)
                    else:
                        current.remove(rid)
                if current:
                    con = await self.bot.db.acquire()
                    async with con.transaction():
                        query = 'UPDATE rolepersists SET roles = $1 WHERE gid = $2 AND uid = $3;'
                        await self.bot.db.execute(query, current, after.guild.id, after.id)
                    await self.bot.db.release(con)
                else:
                    con = await self.bot.db.acquire()
                    async with con.transaction():
                        query = 'DELETE FROM rolepersists WHERE gid = $1 AND uid = $2;'
                        await self.bot.db.execute(query, after.guild.id, after.id)
                    await self.bot.db.release(con)
                self.role_persists[after.guild.id][user.id] = current
                names = ', '.join([
                    discord.utils.escape_mentions(after.guild.get_role(r).name) for r in current if after.guild.get_role(r)
                ])  # The check for if the role exists should be pointless but better to check than error
                logch = self.bot.get_config(after.guild.id).get('log.moderation')
                if logch:
                    embed = discord.Embed(
                        color=discord.Color.green() if current else discord.Color.red(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                    embed.set_author(name=f'Role Persist | {after}', icon_url=str(after.avatar_url_as(static_format='png', size=2048)))
                    embed.add_field(name='User', value=f'{after} ({after.id})', inline=False)
                    embed.add_field(name='Moderator', value=after.guild.me.mention, inline=False)
                    if names:
                        embed.add_field(name='Roles', value=names, inline=False)
                    embed.set_footer(text=f'User ID: {after.id} | Mod ID: {after.guild.me.id}')
                    try:
                        await logch.send(embed=embed)
                    except Exception:
                        pass

    async def cog_check(self, ctx):
        if not ctx.guild or not ctx.guild.id in self.bot.premium_guilds:
            return False
        return True

    @commands.command(aliases=['rolepersists', 'persistroles', 'persistrole'])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rolepersist(self, ctx, user: UserWithFallback, *roles: Role):
        insert = False
        delete = False
        if role.is_default() or role.position >= ctx.guild.me.top_role.position or role.managed:
            return await ctx.error(f'I cannot give users this role')
        if ctx.guild.id not in self.role_persists:
            self.role_persists[ctx.guild.id] = {}
        if user.id not in self.role_persists[ctx.guild.id]:
            insert = True
            self.role_persists[ctx.guild.id][user.id] = []
        roleids = [r.id for r in roles]
        current = [r for r in self.role_persists[ctx.guild.id][user.id]]
        for rid in roleids:
            if rid not in current:
                current.append(rid)
            else:
                current.remove(rid)
        if not current:
            delete = True
        if delete:
            con = await self.bot.db.acquire()
            async with con.transaction():
                query = 'DELETE FROM rolepersists WHERE gid = $1 AND uid = $2;'
                await self.bot.db.execute(query, ctx.guild.id, user.id)
            await self.bot.db.release(con)
        elif not insert:
            con = await self.bot.db.acquire()
            async with con.transaction():
                query = 'UPDATE rolepersists SET roles = $1 WHERE gid = $2 AND uid = $3;'
                await self.bot.db.execute(query, current, ctx.guild.id, user.id)
            await self.bot.db.release(con)
        else:
            con = await self.bot.db.acquire()
            async with con.transaction():
                query = 'INSERT INTO rolepersists (\"gid\", \"uid\", \"roles\") VALUES ($1, $2, $3);'
                await self.bot.db.execute(query, ctx.guild.id, user.id, current)
            await self.bot.db.release(con)
        self.role_persists[ctx.guild.id][user.id] = current
        names = ', '.join([
            discord.utils.escape_mentions(ctx.guild.get_role(r).name) for r in current if ctx.guild.get_role(r)
        ])  # The check for if the role exists should be pointless but better to check than error
        logch = ctx.config.get('log.moderation')
        if logch:
            embed = discord.Embed(
                color=discord.Color.green() if not delete else discord.Color.red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_author(name=f'Role Persist | {user}', icon_url=str(user.avatar_url_as(static_format='png', size=2048)))
            embed.add_field(name='User', value=f'{user} ({user.id})', inline=False)
            embed.add_field(name='Moderator', value=ctx.author.mention, inline=False)
            if names:
                embed.add_field(name='Roles', value=names, inline=False)
            embed.set_footer(text=f'User ID: {user.id} | Mod ID: {ctx.author.id}')
            try:
                await logch.send(embed=embed)
            except Exception:
                pass
        if names:
            return await ctx.success(f'{discord.utils.escape_mentions(str(user))} now has the roles {names} persisted to them')
        else:
            return await ctx.success(f'{discord.utils.escape_mentions(str(user))} no longer has any persisted roles.')


def setup(bot):
    try:
        bot.add_cog(RolePersist(bot))
        bot.logger.info(f'$GREENLoaded $CYAN"role persist" $GREENmodule!')
    except Exception as e:
        # errortb = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        bot.logger.error(f'$REDError while adding module $CYAN"role persist"', exc_info=e)
