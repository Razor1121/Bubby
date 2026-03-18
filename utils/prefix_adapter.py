"""Helpers to route prefix commands through slash command handlers."""

from __future__ import annotations

import discord
from discord.ext import commands


class _ResponseAdapter:
    def __init__(self, ctx: commands.Context):
        self._ctx = ctx
        self._done = False

    async def defer(self, *, ephemeral: bool = False) -> None:
        self._done = True

    async def send_message(self, content=None, **kwargs):
        self._done = True
        await self._ctx.send(content=content, **_strip_ephemeral(kwargs))

    def is_done(self) -> bool:
        return self._done


class _FollowupAdapter:
    def __init__(self, ctx: commands.Context):
        self._ctx = ctx

    async def send(self, content=None, **kwargs):
        await self._ctx.send(content=content, **_strip_ephemeral(kwargs))


class PrefixInteractionAdapter:
    """Minimal interaction-like object for reusing slash command callbacks."""

    def __init__(self, ctx: commands.Context):
        self._ctx = ctx
        self.user = ctx.author
        self.guild = ctx.guild
        self.guild_id = ctx.guild.id if ctx.guild else None
        self.channel = ctx.channel
        self.response = _ResponseAdapter(ctx)
        self.followup = _FollowupAdapter(ctx)


def _strip_ephemeral(kwargs: dict) -> dict:
    data = dict(kwargs)
    data.pop("ephemeral", None)
    return data


def as_interaction(ctx: commands.Context) -> PrefixInteractionAdapter:
    return PrefixInteractionAdapter(ctx)
