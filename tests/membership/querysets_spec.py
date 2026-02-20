from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db.models import Q
from django.utils import timezone

from membership.models import Lease, Member, MembershipPlan, Space, _active_lease_q


def _make_plan(**kwargs):
    defaults = {"name": "Basic", "monthly_price": Decimal("100.00")}
    defaults.update(kwargs)
    return MembershipPlan.objects.create(**defaults)


def _make_member(plan, **kwargs):
    defaults = {
        "full_legal_name": "Test Member",
        "email": "test@example.com",
        "membership_plan": plan,
        "join_date": date(2024, 1, 1),
        "status": Member.Status.ACTIVE,
    }
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


def _make_space(**kwargs):
    defaults = {
        "space_id": "S-001",
        "space_type": Space.SpaceType.STUDIO,
        "status": Space.Status.AVAILABLE,
    }
    defaults.update(kwargs)
    return Space.objects.create(**defaults)


def _make_lease(member, space, **kwargs):
    defaults = {
        "member": member,
        "space": space,
        "lease_type": Lease.LeaseType.MONTH_TO_MONTH,
        "base_price": Decimal("500.00"),
        "monthly_rent": Decimal("500.00"),
        "start_date": date(2024, 1, 1),
    }
    defaults.update(kwargs)
    return Lease.objects.create(**defaults)


def describe_active_lease_q():
    def it_builds_q_with_default_prefix_and_today():
        ref = date(2025, 6, 15)
        with patch("membership.models.timezone") as mock_tz:
            mock_tz.now.return_value.date.return_value = ref
            q = _active_lease_q()

        expected = Q(start_date__lte=ref) & (Q(end_date__isnull=True) | Q(end_date__gte=ref))
        assert q == expected

    def it_uses_explicit_today_parameter():
        ref = date(2024, 12, 25)
        q = _active_lease_q(today=ref)

        expected = Q(start_date__lte=ref) & (Q(end_date__isnull=True) | Q(end_date__gte=ref))
        assert q == expected

    def it_applies_prefix_to_field_names():
        ref = date(2025, 1, 1)
        q = _active_lease_q(prefix="lease__", today=ref)

        expected = Q(lease__start_date__lte=ref) & (Q(lease__end_date__isnull=True) | Q(lease__end_date__gte=ref))
        assert q == expected

    def it_applies_leases_prefix_for_related_lookups():
        ref = date(2025, 3, 10)
        q = _active_lease_q(prefix="leases__", today=ref)

        expected = Q(leases__start_date__lte=ref) & (Q(leases__end_date__isnull=True) | Q(leases__end_date__gte=ref))
        assert q == expected


@pytest.mark.django_db
def describe_member_queryset():
    def describe_active():
        def it_returns_only_active_members():
            plan = _make_plan()
            active = _make_member(plan, full_legal_name="Active One", email="a@x.com")
            _make_member(
                plan,
                full_legal_name="Former One",
                email="f@x.com",
                status=Member.Status.FORMER,
            )
            _make_member(
                plan,
                full_legal_name="Suspended One",
                email="s@x.com",
                status=Member.Status.SUSPENDED,
            )

            result = list(Member.objects.active())
            assert result == [active]

        def it_excludes_former_members():
            plan = _make_plan()
            _make_member(
                plan,
                full_legal_name="Former",
                email="f@x.com",
                status=Member.Status.FORMER,
            )

            assert Member.objects.active().count() == 0

        def it_excludes_suspended_members():
            plan = _make_plan()
            _make_member(
                plan,
                full_legal_name="Suspended",
                email="s@x.com",
                status=Member.Status.SUSPENDED,
            )

            assert Member.objects.active().count() == 0

    def describe_with_lease_totals():
        def it_annotates_active_lease_count():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            today = timezone.now().date()

            space1 = _make_space(space_id="S-001")
            space2 = _make_space(space_id="S-002")

            # Two active leases
            _make_lease(
                member,
                space1,
                start_date=today - timedelta(days=30),
                monthly_rent=Decimal("300.00"),
            )
            _make_lease(
                member,
                space2,
                start_date=today - timedelta(days=10),
                monthly_rent=Decimal("200.00"),
            )

            # One ended lease - should not count
            space3 = _make_space(space_id="S-003")
            _make_lease(
                member,
                space3,
                start_date=today - timedelta(days=90),
                end_date=today - timedelta(days=1),
                monthly_rent=Decimal("100.00"),
            )

            annotated = Member.objects.with_lease_totals().get(pk=member.pk)
            assert annotated.active_lease_count == 2

        def it_annotates_total_monthly_rent():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            today = timezone.now().date()

            space1 = _make_space(space_id="S-001")
            space2 = _make_space(space_id="S-002")

            _make_lease(
                member,
                space1,
                start_date=today - timedelta(days=30),
                monthly_rent=Decimal("300.00"),
            )
            _make_lease(
                member,
                space2,
                start_date=today - timedelta(days=10),
                monthly_rent=Decimal("200.00"),
            )

            annotated = Member.objects.with_lease_totals().get(pk=member.pk)
            assert annotated.total_monthly_rent == Decimal("500.00")

        def it_handles_members_with_no_leases():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")

            annotated = Member.objects.with_lease_totals().get(pk=member.pk)
            assert annotated.active_lease_count == 0
            assert annotated.total_monthly_rent == Decimal("0.00")


@pytest.mark.django_db
def describe_space_queryset():
    def describe_available():
        def it_returns_only_available_spaces():
            available = _make_space(space_id="S-001", status=Space.Status.AVAILABLE)
            _make_space(space_id="S-002", status=Space.Status.OCCUPIED)
            _make_space(space_id="S-003", status=Space.Status.MAINTENANCE)

            result = list(Space.objects.available())
            assert result == [available]

        def it_excludes_occupied_spaces():
            _make_space(space_id="S-001", status=Space.Status.OCCUPIED)

            assert Space.objects.available().count() == 0

        def it_excludes_maintenance_spaces():
            _make_space(space_id="S-001", status=Space.Status.MAINTENANCE)

            assert Space.objects.available().count() == 0

    def describe_with_revenue():
        def it_annotates_active_lease_revenue():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            space = _make_space(space_id="S-001", status=Space.Status.OCCUPIED)
            today = timezone.now().date()

            _make_lease(
                member,
                space,
                start_date=today - timedelta(days=30),
                monthly_rent=Decimal("750.00"),
            )

            annotated = Space.objects.with_revenue().get(pk=space.pk)
            assert annotated.active_lease_rent_total == Decimal("750.00")

        def it_handles_spaces_with_no_leases():
            _make_space(space_id="S-001")

            annotated = Space.objects.with_revenue().get(space_id="S-001")
            assert annotated.active_lease_rent_total == Decimal("0.00")


@pytest.mark.django_db
def describe_lease_queryset():
    def describe_active():
        def it_returns_leases_active_today():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            space = _make_space(space_id="S-001")
            today = timezone.now().date()

            active_lease = _make_lease(
                member,
                space,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=30),
            )

            result = list(Lease.objects.active())
            assert result == [active_lease]

        def it_returns_leases_active_as_of_specific_date():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            space = _make_space(space_id="S-001")

            lease = _make_lease(
                member,
                space,
                start_date=date(2024, 3, 1),
                end_date=date(2024, 6, 30),
            )

            # Should include when as_of is within range
            result = list(Lease.objects.active(as_of=date(2024, 4, 15)))
            assert result == [lease]

            # Should exclude when as_of is outside range
            result = list(Lease.objects.active(as_of=date(2024, 7, 1)))
            assert result == []

        def it_excludes_ended_leases():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            space = _make_space(space_id="S-001")
            today = timezone.now().date()

            _make_lease(
                member,
                space,
                start_date=today - timedelta(days=90),
                end_date=today - timedelta(days=1),
            )

            assert Lease.objects.active().count() == 0

        def it_excludes_future_leases():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            space = _make_space(space_id="S-001")
            today = timezone.now().date()

            _make_lease(
                member,
                space,
                start_date=today + timedelta(days=30),
                end_date=today + timedelta(days=90),
            )

            assert Lease.objects.active().count() == 0

        def it_includes_ongoing_leases_with_no_end_date():
            plan = _make_plan()
            member = _make_member(plan, email="m@x.com")
            space = _make_space(space_id="S-001")
            today = timezone.now().date()

            ongoing = _make_lease(
                member,
                space,
                start_date=today - timedelta(days=60),
                end_date=None,
            )

            result = list(Lease.objects.active())
            assert result == [ongoing]
