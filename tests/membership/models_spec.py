"""Tests for membership models."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from membership.models import DEFAULT_PRICE_PER_SQFT, Lease, Member, MembershipPlan, Space

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(**kwargs):
    defaults = {"name": "Basic", "monthly_price": Decimal("150.00")}
    defaults.update(kwargs)
    return MembershipPlan.objects.create(**defaults)


def _make_member(plan=None, **kwargs):
    if plan is None:
        plan = _make_plan()
    defaults = {
        "full_legal_name": "Jane Doe",
        "email": "jane@example.com",
        "membership_plan": plan,
        "join_date": date(2024, 1, 1),
    }
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


def _make_space(**kwargs):
    defaults = {
        "space_id": "S-100",
        "space_type": Space.SpaceType.STUDIO,
    }
    defaults.update(kwargs)
    return Space.objects.create(**defaults)


def _make_lease(member=None, space=None, **kwargs):
    if member is None:
        member = _make_member()
    if space is None:
        space = _make_space()
    today = timezone.now().date()
    defaults = {
        "member": member,
        "space": space,
        "lease_type": Lease.LeaseType.MONTH_TO_MONTH,
        "base_price": Decimal("200.00"),
        "monthly_rent": Decimal("200.00"),
        "start_date": today - timedelta(days=30),
    }
    defaults.update(kwargs)
    return Lease.objects.create(**defaults)


# ---------------------------------------------------------------------------
# MembershipPlan
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def describe_membership_plan():
    def it_has_str_representation():
        plan = _make_plan(name="Premium Studio")
        assert str(plan) == "Premium Studio"

    def it_stores_monthly_price():
        plan = _make_plan(monthly_price=Decimal("275.50"))
        plan.refresh_from_db()
        assert plan.monthly_price == Decimal("275.50")

    def it_allows_nullable_deposit():
        plan_no_deposit = _make_plan(name="No Deposit Plan")
        assert plan_no_deposit.deposit_required is None

        plan_with_deposit = _make_plan(
            name="With Deposit Plan",
            deposit_required=Decimal("500.00"),
        )
        plan_with_deposit.refresh_from_db()
        assert plan_with_deposit.deposit_required == Decimal("500.00")


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def describe_member():
    def it_has_str_representation():
        member = _make_member(preferred_name="JD")
        assert str(member) == "JD"

    def describe_display_name():
        def it_returns_preferred_name_when_set():
            member = _make_member(
                full_legal_name="Jane Doe",
                preferred_name="JD",
            )
            assert member.display_name == "JD"

        def it_returns_full_legal_name_when_no_preferred_name():
            member = _make_member(
                full_legal_name="Jane Doe",
                preferred_name="",
            )
            assert member.display_name == "Jane Doe"

    def it_defaults_to_active_status():
        member = _make_member()
        assert member.status == Member.Status.ACTIVE

    def it_defaults_to_standard_role():
        member = _make_member()
        assert member.role == Member.Role.STANDARD

    def it_allows_null_user():
        member = _make_member(user=None)
        assert member.user is None

    def it_stores_committed_until():
        member = _make_member(committed_until=date(2025, 6, 30))
        member.refresh_from_db()
        assert member.committed_until == date(2025, 6, 30)

    def it_allows_null_committed_until():
        member = _make_member()
        assert member.committed_until is None


@pytest.mark.django_db
def describe_member_computed_properties():
    def it_calculates_membership_monthly_dues():
        plan = _make_plan(monthly_price=Decimal("250.00"))
        member = _make_member(plan=plan)
        assert member.membership_monthly_dues == Decimal("250.00")

    def it_calculates_studio_storage_total_with_active_leases():
        plan = _make_plan(monthly_price=Decimal("150.00"))
        member = _make_member(plan=plan)
        today = timezone.now().date()

        space_a = _make_space(space_id="S-A")
        space_b = _make_space(space_id="S-B")

        _make_lease(
            member=member,
            space=space_a,
            monthly_rent=Decimal("300.00"),
            start_date=today - timedelta(days=10),
        )
        _make_lease(
            member=member,
            space=space_b,
            monthly_rent=Decimal("150.00"),
            start_date=today - timedelta(days=5),
        )

        assert member.studio_storage_total == Decimal("450.00")

    def it_returns_zero_studio_storage_with_no_leases():
        member = _make_member()
        assert member.studio_storage_total == Decimal("0.00")

    def it_calculates_total_monthly_spend():
        plan = _make_plan(monthly_price=Decimal("200.00"))
        member = _make_member(plan=plan)
        today = timezone.now().date()

        space = _make_space(space_id="S-TMS")
        _make_lease(
            member=member,
            space=space,
            monthly_rent=Decimal("100.00"),
            start_date=today - timedelta(days=10),
        )

        assert member.total_monthly_spend == Decimal("300.00")


@pytest.mark.django_db
def describe_member_leases_and_spaces():
    def describe_active_leases():
        def it_returns_active_leases():
            member = _make_member()
            today = timezone.now().date()

            space_active = _make_space(space_id="S-ACT")
            space_ended = _make_space(space_id="S-END")
            space_future = _make_space(space_id="S-FUT")

            active_lease = _make_lease(
                member=member,
                space=space_active,
                start_date=today - timedelta(days=30),
            )
            _make_lease(
                member=member,
                space=space_ended,
                start_date=today - timedelta(days=60),
                end_date=today - timedelta(days=1),
            )
            _make_lease(
                member=member,
                space=space_future,
                start_date=today + timedelta(days=30),
            )

            active = list(member.active_leases)
            assert len(active) == 1
            assert active[0].pk == active_lease.pk

        def it_includes_ongoing_lease_with_no_end_date():
            member = _make_member()
            today = timezone.now().date()
            space = _make_space(space_id="S-ONG")
            ongoing = _make_lease(
                member=member,
                space=space,
                start_date=today - timedelta(days=10),
                end_date=None,
            )
            active = list(member.active_leases)
            assert len(active) == 1
            assert active[0].pk == ongoing.pk

    def describe_current_spaces():
        def it_returns_current_spaces():
            member = _make_member()
            today = timezone.now().date()

            space = _make_space(space_id="S-CUR")
            _make_lease(
                member=member,
                space=space,
                start_date=today - timedelta(days=10),
            )

            spaces = list(member.current_spaces)
            assert len(spaces) == 1
            assert spaces[0].pk == space.pk


# ---------------------------------------------------------------------------
# Space
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def describe_space():
    def it_has_str_representation():
        space = _make_space(space_id="A-101", name="Corner Studio")
        assert str(space) == "A-101 - Corner Studio"

    def it_has_str_representation_without_name():
        space = _make_space(space_id="A-102", name="")
        assert str(space) == "A-102"

    def describe_full_price():
        def it_uses_manual_price_when_set():
            space = _make_space(
                space_id="S-MP",
                manual_price=Decimal("500.00"),
                size_sqft=Decimal("100.00"),
            )
            assert space.full_price == Decimal("500.00")

        def it_calculates_from_sqft_when_no_manual_price():
            space = _make_space(
                space_id="S-SQ",
                manual_price=None,
                size_sqft=Decimal("100.00"),
            )
            expected = Decimal("100.00") * DEFAULT_PRICE_PER_SQFT
            assert space.full_price == expected

        def it_returns_none_when_no_size_or_manual_price():
            space = _make_space(
                space_id="S-NO",
                manual_price=None,
                size_sqft=None,
            )
            assert space.full_price is None


@pytest.mark.django_db
def describe_space_vacancy_value():
    def it_returns_full_price_when_available():
        space = _make_space(
            space_id="S-VA",
            status=Space.Status.AVAILABLE,
            manual_price=Decimal("400.00"),
        )
        assert space.vacancy_value == Decimal("400.00")

    def it_returns_zero_when_occupied():
        space = _make_space(
            space_id="S-OC",
            status=Space.Status.OCCUPIED,
            manual_price=Decimal("400.00"),
        )
        assert space.vacancy_value == Decimal("0.00")

    def it_returns_zero_when_available_but_no_price():
        space = _make_space(
            space_id="S-NP",
            status=Space.Status.AVAILABLE,
            manual_price=None,
            size_sqft=None,
        )
        assert space.vacancy_value == Decimal("0.00")


@pytest.mark.django_db
def describe_space_occupants_and_revenue():
    def describe_current_occupants():
        def it_returns_current_occupants():
            plan = _make_plan(name="Occ Plan")
            member = _make_member(plan=plan)
            today = timezone.now().date()
            space = _make_space(space_id="S-OCC")

            _make_lease(
                member=member,
                space=space,
                start_date=today - timedelta(days=10),
            )

            occupants = list(space.current_occupants)
            assert len(occupants) == 1
            assert occupants[0].pk == member.pk

        def it_excludes_ended_leases():
            plan = _make_plan(name="Occ Plan 2")
            member = _make_member(plan=plan)
            today = timezone.now().date()
            space = _make_space(space_id="S-OC2")

            _make_lease(
                member=member,
                space=space,
                start_date=today - timedelta(days=60),
                end_date=today - timedelta(days=1),
            )

            occupants = list(space.current_occupants)
            assert len(occupants) == 0

    def describe_revenue():
        def it_calculates_actual_revenue_from_active_leases():
            plan = _make_plan(name="Rev Plan")
            member_a = _make_member(plan=plan, full_legal_name="Alice", email="alice@example.com")
            member_b = _make_member(plan=plan, full_legal_name="Bob", email="bob@example.com")
            today = timezone.now().date()
            space = _make_space(space_id="S-REV", manual_price=Decimal("600.00"))

            _make_lease(
                member=member_a,
                space=space,
                monthly_rent=Decimal("300.00"),
                start_date=today - timedelta(days=10),
            )
            _make_lease(
                member=member_b,
                space=space,
                monthly_rent=Decimal("200.00"),
                start_date=today - timedelta(days=5),
            )

            assert space.actual_revenue == Decimal("500.00")

        def it_returns_zero_revenue_with_no_active_leases():
            space = _make_space(space_id="S-NR")
            assert space.actual_revenue == Decimal("0.00")

        def it_calculates_revenue_loss():
            space = _make_space(
                space_id="S-RL",
                manual_price=Decimal("600.00"),
            )
            plan = _make_plan(name="RL Plan")
            member = _make_member(plan=plan, email="rl@example.com")
            today = timezone.now().date()

            _make_lease(
                member=member,
                space=space,
                monthly_rent=Decimal("400.00"),
                start_date=today - timedelta(days=5),
            )

            assert space.revenue_loss == Decimal("200.00")

        def it_returns_none_revenue_loss_when_no_full_price():
            space = _make_space(
                space_id="S-NRL",
                manual_price=None,
                size_sqft=None,
            )
            assert space.revenue_loss is None


# ---------------------------------------------------------------------------
# Lease
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def describe_lease():
    def it_has_str_representation():
        plan = _make_plan(name="Lease Plan")
        member = _make_member(
            plan=plan,
            full_legal_name="Test User",
            preferred_name="TU",
            email="tu@example.com",
        )
        space = _make_space(space_id="L-100", name="Main")
        lease = _make_lease(
            member=member,
            space=space,
            start_date=date(2024, 3, 1),
        )
        assert str(lease) == "TU @ L-100 - Main (2024-03-01)"

    def it_stores_committed_until():
        lease = _make_lease(committed_until=date(2025, 12, 31))
        lease.refresh_from_db()
        assert lease.committed_until == date(2025, 12, 31)

    def it_allows_null_committed_until():
        lease = _make_lease()
        assert lease.committed_until is None


@pytest.mark.django_db
def describe_lease_is_active():
    def it_is_active_when_ongoing():
        """Ongoing lease: started in the past, no end_date."""
        today = timezone.now().date()
        lease = _make_lease(
            start_date=today - timedelta(days=30),
            end_date=None,
        )
        assert lease.is_active is True

    def it_is_active_when_within_date_range():
        today = timezone.now().date()
        lease = _make_lease(
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=30),
        )
        assert lease.is_active is True

    def it_is_active_when_end_date_is_today():
        today = timezone.now().date()
        lease = _make_lease(
            start_date=today - timedelta(days=30),
            end_date=today,
        )
        assert lease.is_active is True

    def it_is_active_when_start_date_is_today():
        today = timezone.now().date()
        lease = _make_lease(
            start_date=today,
            end_date=None,
        )
        assert lease.is_active is True

    def it_is_not_active_when_ended():
        today = timezone.now().date()
        lease = _make_lease(
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=1),
        )
        assert lease.is_active is False

    def it_is_not_active_when_not_started():
        today = timezone.now().date()
        lease = _make_lease(
            start_date=today + timedelta(days=1),
        )
        assert lease.is_active is False
