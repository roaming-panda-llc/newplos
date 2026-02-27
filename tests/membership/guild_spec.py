"""Tests for Guild and GuildVote models."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from membership.models import Guild, GuildVote, Member
from tests.membership.factories import (
    GuildFactory,
    GuildVoteFactory,
    LeaseFactory,
    MemberFactory,
    SpaceFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Guild
# ---------------------------------------------------------------------------


def describe_Guild():
    def it_creates_with_factory():
        guild = GuildFactory(name="Test Guild")
        assert guild.name == "Test Guild"
        assert guild.pk is not None

    def it_has_str_representation():
        guild = GuildFactory(name="Ceramics Guild")
        assert str(guild) == "Ceramics Guild"

    def it_can_have_guild_lead():
        member = MemberFactory()
        guild = GuildFactory(guild_lead=member)
        assert guild.guild_lead == member

    def it_allows_null_guild_lead():
        guild = GuildFactory(guild_lead=None)
        assert guild.guild_lead is None

    def it_has_notes_field():
        guild = GuildFactory(name="Notes Guild", notes="Some important notes")
        guild.refresh_from_db()
        assert guild.notes == "Some important notes"

    def it_has_created_at():
        guild = GuildFactory()
        assert guild.created_at is not None

    def it_enforces_unique_name():
        GuildFactory(name="Unique Guild")
        with pytest.raises(IntegrityError):
            GuildFactory(name="Unique Guild")


def describe_Guild_active_leases():
    def it_returns_active_leases():
        guild = GuildFactory()
        today = timezone.now().date()
        space = SpaceFactory()
        lease = LeaseFactory(
            tenant_obj=guild,
            space=space,
            start_date=today - timedelta(days=10),
        )
        active = list(guild.active_leases)
        assert len(active) == 1
        assert active[0].pk == lease.pk

    def it_excludes_ended_leases():
        guild = GuildFactory()
        today = timezone.now().date()
        space = SpaceFactory()
        LeaseFactory(
            tenant_obj=guild,
            space=space,
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=1),
        )
        active = list(guild.active_leases)
        assert len(active) == 0

    def it_excludes_future_leases():
        guild = GuildFactory()
        today = timezone.now().date()
        space = SpaceFactory()
        LeaseFactory(
            tenant_obj=guild,
            space=space,
            start_date=today + timedelta(days=30),
        )
        active = list(guild.active_leases)
        assert len(active) == 0


def describe_Guild_ordering():
    def it_orders_by_name():
        g2 = GuildFactory(name="Zebra Guild")
        g1 = GuildFactory(name="Alpha Guild")
        guilds = list(Guild.objects.all())
        assert guilds == [g1, g2]


# ---------------------------------------------------------------------------
# GuildVote
# ---------------------------------------------------------------------------


def describe_GuildVote():
    def it_creates_with_factory():
        vote = GuildVoteFactory()
        assert vote.pk is not None

    def it_has_str_representation():
        vote = GuildVoteFactory(priority=1)
        assert "\u2192" in str(vote)
        assert "#1" in str(vote)

    def it_stores_priority():
        vote = GuildVoteFactory(priority=2)
        assert vote.priority == 2

    def it_references_member_and_guild():
        member = MemberFactory()
        guild = GuildFactory()
        vote = GuildVoteFactory(member=member, guild=guild, priority=1)
        assert vote.member == member
        assert vote.guild == guild

    def describe_unique_constraints():
        def it_enforces_unique_member_priority():
            vote1 = GuildVoteFactory(priority=1)
            with pytest.raises(IntegrityError):
                GuildVoteFactory(member=vote1.member, priority=1, guild=GuildFactory())

        def it_enforces_unique_member_guild():
            vote1 = GuildVoteFactory(priority=1)
            with pytest.raises(IntegrityError):
                GuildVoteFactory(member=vote1.member, guild=vote1.guild, priority=2)

    def describe_ordering():
        def it_orders_by_member_then_priority():
            member = MemberFactory(full_legal_name="Test Member")
            guild_a = GuildFactory(name="Guild A")
            guild_b = GuildFactory(name="Guild B")
            v2 = GuildVoteFactory(member=member, guild=guild_b, priority=2)
            v1 = GuildVoteFactory(member=member, guild=guild_a, priority=1)
            votes = list(GuildVote.objects.filter(member=member))
            assert votes == [v1, v2]


# ---------------------------------------------------------------------------
# Lease with Guild tenant (GenericFK)
# ---------------------------------------------------------------------------


def describe_lease_with_guild_tenant():
    def it_creates_lease_for_guild():
        guild = GuildFactory(name="Pottery Guild")
        space = SpaceFactory()
        today = timezone.now().date()
        lease = LeaseFactory(
            tenant_obj=guild,
            space=space,
            start_date=today - timedelta(days=5),
        )
        assert lease.tenant == guild
        assert lease.pk is not None

    def it_has_str_representation_with_guild():
        guild = GuildFactory(name="Woodworking")
        space = SpaceFactory(space_id="W-100", name="Workshop")
        lease = LeaseFactory(
            tenant_obj=guild,
            space=space,
            start_date=date(2024, 6, 1),
        )
        assert str(lease) == "Woodworking @ W-100 - Workshop (2024-06-01)"

    def it_appears_in_space_current_occupants():
        guild = GuildFactory(name="Current Occupant Guild")
        space = SpaceFactory()
        today = timezone.now().date()
        LeaseFactory(
            tenant_obj=guild,
            space=space,
            start_date=today - timedelta(days=5),
        )
        occupants = space.current_occupants
        assert len(occupants) == 1
        assert occupants[0] == guild

    def it_mixes_member_and_guild_occupants():
        member = MemberFactory()
        guild = GuildFactory()
        space = SpaceFactory()
        today = timezone.now().date()
        LeaseFactory(
            tenant_obj=member,
            space=space,
            start_date=today - timedelta(days=10),
            monthly_rent=Decimal("200.00"),
        )
        LeaseFactory(
            tenant_obj=guild,
            space=space,
            start_date=today - timedelta(days=5),
            monthly_rent=Decimal("300.00"),
        )
        occupants = space.current_occupants
        assert len(occupants) == 2
        occupant_types = {type(o) for o in occupants}
        assert Member in occupant_types
        assert Guild in occupant_types

    def it_calculates_space_revenue_with_guild_lease():
        guild = GuildFactory()
        space = SpaceFactory(manual_price=Decimal("800.00"))
        today = timezone.now().date()
        LeaseFactory(
            tenant_obj=guild,
            space=space,
            monthly_rent=Decimal("500.00"),
            start_date=today - timedelta(days=5),
        )
        assert space.actual_revenue == Decimal("500.00")


# ---------------------------------------------------------------------------
