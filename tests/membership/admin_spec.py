from datetime import date
from decimal import Decimal

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.utils import timezone

from membership.admin import (
    LeaseAdmin,
    LeaseInlineMember,
    LeaseInlineSpace,
    MemberAdmin,
    MembershipPlanAdmin,
    SpaceAdmin,
)
from membership.models import Lease, Member, MembershipPlan, Space

User = get_user_model()


def describe_admin_registration():
    def it_registers_membership_plan():
        assert MembershipPlan in admin.site._registry
        assert isinstance(admin.site._registry[MembershipPlan], MembershipPlanAdmin)

    def it_registers_member():
        assert Member in admin.site._registry
        assert isinstance(admin.site._registry[Member], MemberAdmin)

    def it_registers_space():
        assert Space in admin.site._registry
        assert isinstance(admin.site._registry[Space], SpaceAdmin)

    def it_registers_lease():
        assert Lease in admin.site._registry
        assert isinstance(admin.site._registry[Lease], LeaseAdmin)


def describe_MemberAdmin():
    def it_has_lease_inline():
        member_admin = admin.site._registry[Member]
        assert LeaseInlineMember in member_admin.inlines

    def it_has_expected_list_display():
        member_admin = admin.site._registry[Member]
        assert member_admin.list_display == [
            "display_name",
            "email",
            "membership_plan",
            "status",
            "role",
            "join_date",
            "total_monthly_spend_display",
        ]

    def it_has_expected_search_fields():
        member_admin = admin.site._registry[Member]
        assert member_admin.search_fields == [
            "full_legal_name",
            "preferred_name",
            "email",
        ]

    def it_has_expected_list_filter():
        member_admin = admin.site._registry[Member]
        assert member_admin.list_filter == ["status", "role", "membership_plan"]


def describe_SpaceAdmin():
    def it_has_lease_inline():
        space_admin = admin.site._registry[Space]
        assert LeaseInlineSpace in space_admin.inlines

    def it_has_expected_list_display():
        space_admin = admin.site._registry[Space]
        assert space_admin.list_display == [
            "space_id",
            "name",
            "space_type",
            "size_sqft",
            "full_price_display",
            "actual_revenue_display",
            "vacancy_value_display",
            "status",
        ]

    def it_has_expected_search_fields():
        space_admin = admin.site._registry[Space]
        assert space_admin.search_fields == ["space_id", "name"]


def describe_LeaseAdmin():
    def it_has_expected_list_display():
        lease_admin = admin.site._registry[Lease]
        assert lease_admin.list_display == [
            "member",
            "space",
            "lease_type",
            "monthly_rent",
            "start_date",
            "end_date",
            "is_active_display",
        ]

    def it_has_expected_search_fields():
        lease_admin = admin.site._registry[Lease]
        assert lease_admin.search_fields == [
            "member__full_legal_name",
            "space__space_id",
        ]


@pytest.mark.django_db
def describe_admin_member_computed_fields():
    def it_displays_member_total_monthly_spend():
        plan = MembershipPlan.objects.create(
            name="Basic Plan",
            monthly_price=Decimal("100.00"),
        )
        member = Member.objects.create(
            full_legal_name="Test User",
            email="test@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        member_admin = admin.site._registry[Member]
        factory = RequestFactory()
        request = factory.get("/admin/membership/member/")
        annotated_member = member_admin.get_queryset(request).get(pk=member.pk)
        result = member_admin.total_monthly_spend_display(annotated_member)
        assert result == "$100.00"

    def it_displays_member_total_monthly_spend_with_leases():
        plan = MembershipPlan.objects.create(
            name="Lease Spend Plan",
            monthly_price=Decimal("100.00"),
        )
        member = Member.objects.create(
            full_legal_name="Lease Spender",
            email="lease-spend@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        space = Space.objects.create(
            space_id="S-SPEND",
            space_type="studio",
            status="occupied",
        )
        today = timezone.now().date()
        Lease.objects.create(
            member=member,
            space=space,
            lease_type="month_to_month",
            base_price=Decimal("200.00"),
            monthly_rent=Decimal("200.00"),
            start_date=today,
        )
        member_admin = admin.site._registry[Member]
        factory = RequestFactory()
        request = factory.get("/admin/membership/member/")
        annotated_member = member_admin.get_queryset(request).get(pk=member.pk)
        result = member_admin.total_monthly_spend_display(annotated_member)
        assert result == "$300.00"

    def it_displays_member_display_name():
        plan = MembershipPlan.objects.create(
            name="Display Name Plan",
            monthly_price=Decimal("75.00"),
        )
        member = Member.objects.create(
            full_legal_name="John Smith",
            preferred_name="Johnny",
            email="johnny@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        member_admin = admin.site._registry[Member]
        result = member_admin.display_name(member)
        assert result == "Johnny"

    def it_displays_membership_plan_member_count():
        plan = MembershipPlan.objects.create(
            name="Counted Plan",
            monthly_price=Decimal("100.00"),
        )
        Member.objects.create(
            full_legal_name="Count Member 1",
            email="count1@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        Member.objects.create(
            full_legal_name="Count Member 2",
            email="count2@example.com",
            membership_plan=plan,
            join_date=date(2024, 2, 1),
        )
        plan_admin = admin.site._registry[MembershipPlan]
        factory = RequestFactory()
        request = factory.get("/admin/membership/membershipplan/")
        qs = plan_admin.get_queryset(request)
        annotated_plan = qs.get(pk=plan.pk)
        result = plan_admin.member_count(annotated_plan)
        assert result == 2


@pytest.mark.django_db
def describe_admin_space_computed_fields():
    def it_displays_space_full_price_with_manual_price():
        space = Space.objects.create(
            space_id="S-001",
            space_type="studio",
            manual_price=Decimal("500.00"),
            status="available",
        )
        space_admin = admin.site._registry[Space]
        result = space_admin.full_price_display(space)
        assert result == "$500.00"

    def it_displays_space_full_price_calculated_from_sqft():
        space = Space.objects.create(
            space_id="S-002",
            space_type="studio",
            size_sqft=Decimal("100.00"),
            status="available",
        )
        space_admin = admin.site._registry[Space]
        result = space_admin.full_price_display(space)
        assert result == "$375.00"

    def it_displays_space_full_price_dash_when_none():
        space = Space.objects.create(
            space_id="S-003",
            space_type="other",
            status="available",
        )
        space_admin = admin.site._registry[Space]
        result = space_admin.full_price_display(space)
        assert result == "-"

    def it_displays_space_actual_revenue():
        plan = MembershipPlan.objects.create(
            name="Revenue Plan",
            monthly_price=Decimal("50.00"),
        )
        member = Member.objects.create(
            full_legal_name="Revenue Member",
            email="revenue@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        space = Space.objects.create(
            space_id="S-020",
            space_type="studio",
            status="occupied",
        )
        today = timezone.now().date()
        Lease.objects.create(
            member=member,
            space=space,
            lease_type="month_to_month",
            base_price=Decimal("300.00"),
            monthly_rent=Decimal("300.00"),
            start_date=today,
        )
        space_admin = admin.site._registry[Space]
        factory = RequestFactory()
        request = factory.get("/admin/membership/space/")
        annotated_space = space_admin.get_queryset(request).get(pk=space.pk)
        result = space_admin.actual_revenue_display(annotated_space)
        assert result == "$300.00"

    def it_displays_space_vacancy_value():
        space = Space.objects.create(
            space_id="S-021",
            space_type="studio",
            manual_price=Decimal("400.00"),
            status="available",
        )
        space_admin = admin.site._registry[Space]
        factory = RequestFactory()
        request = factory.get("/admin/membership/space/")
        annotated_space = space_admin.get_queryset(request).get(pk=space.pk)
        result = space_admin.vacancy_value_display(annotated_space)
        assert result == "$400.00"

    def it_displays_space_vacancy_value_zero_when_occupied():
        space = Space.objects.create(
            space_id="S-022",
            space_type="studio",
            manual_price=Decimal("400.00"),
            status="occupied",
        )
        space_admin = admin.site._registry[Space]
        factory = RequestFactory()
        request = factory.get("/admin/membership/space/")
        annotated_space = space_admin.get_queryset(request).get(pk=space.pk)
        result = space_admin.vacancy_value_display(annotated_space)
        assert result == "$0.00"

    def it_displays_vacancy_value_subtracting_active_lease_rent():
        plan = MembershipPlan.objects.create(
            name="Vacancy Subtract Plan",
            monthly_price=Decimal("50.00"),
        )
        member = Member.objects.create(
            full_legal_name="Partial Occupant",
            email="partial@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        space = Space.objects.create(
            space_id="S-023",
            space_type="studio",
            manual_price=Decimal("600.00"),
            status="available",
        )
        today = timezone.now().date()
        Lease.objects.create(
            member=member,
            space=space,
            lease_type="month_to_month",
            base_price=Decimal("200.00"),
            monthly_rent=Decimal("200.00"),
            start_date=today,
        )
        space_admin = admin.site._registry[Space]
        factory = RequestFactory()
        request = factory.get("/admin/membership/space/")
        annotated_space = space_admin.get_queryset(request).get(pk=space.pk)
        result = space_admin.vacancy_value_display(annotated_space)
        assert result == "$400.00"


@pytest.mark.django_db
def describe_admin_lease_and_inline_fields():
    def it_displays_lease_is_active_for_active_lease():
        plan = MembershipPlan.objects.create(
            name="Active Lease Plan",
            monthly_price=Decimal("50.00"),
        )
        member = Member.objects.create(
            full_legal_name="Active Member",
            email="active@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        space = Space.objects.create(
            space_id="S-010",
            space_type="studio",
            status="occupied",
        )
        lease = Lease.objects.create(
            member=member,
            space=space,
            lease_type="month_to_month",
            base_price=Decimal("200.00"),
            monthly_rent=Decimal("200.00"),
            start_date=date(2024, 1, 1),
        )
        lease_admin = admin.site._registry[Lease]
        result = lease_admin.is_active_display(lease)
        assert result is True

    def it_displays_lease_is_active_false_for_expired_lease():
        plan = MembershipPlan.objects.create(
            name="Expired Lease Plan",
            monthly_price=Decimal("50.00"),
        )
        member = Member.objects.create(
            full_legal_name="Expired Member",
            email="expired@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        space = Space.objects.create(
            space_id="S-011",
            space_type="storage",
            status="available",
        )
        lease = Lease.objects.create(
            member=member,
            space=space,
            lease_type="annual",
            base_price=Decimal("100.00"),
            monthly_rent=Decimal("100.00"),
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        lease_admin = admin.site._registry[Lease]
        result = lease_admin.is_active_display(lease)
        assert result is False

    def it_displays_inline_member_is_active():
        plan = MembershipPlan.objects.create(
            name="Inline Member Plan",
            monthly_price=Decimal("50.00"),
        )
        member = Member.objects.create(
            full_legal_name="Inline Member",
            email="inline-member@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        space = Space.objects.create(
            space_id="S-030",
            space_type="studio",
            status="occupied",
        )
        lease = Lease.objects.create(
            member=member,
            space=space,
            lease_type="month_to_month",
            base_price=Decimal("200.00"),
            monthly_rent=Decimal("200.00"),
            start_date=date(2024, 1, 1),
        )
        inline = LeaseInlineMember(Member, admin.site)
        result = inline.is_active_display(lease)
        assert result is True

    def it_displays_inline_space_is_active():
        plan = MembershipPlan.objects.create(
            name="Inline Space Plan",
            monthly_price=Decimal("50.00"),
        )
        member = Member.objects.create(
            full_legal_name="Inline Space Member",
            email="inline-space@example.com",
            membership_plan=plan,
            join_date=date(2024, 1, 1),
        )
        space = Space.objects.create(
            space_id="S-031",
            space_type="studio",
            status="occupied",
        )
        lease = Lease.objects.create(
            member=member,
            space=space,
            lease_type="month_to_month",
            base_price=Decimal("250.00"),
            monthly_rent=Decimal("250.00"),
            start_date=date(2024, 1, 1),
        )
        inline = LeaseInlineSpace(Space, admin.site)
        result = inline.is_active_display(lease)
        assert result is True


def describe_lease_is_active():
    def it_returns_false_when_start_date_is_none():
        lease = Lease(start_date=None)
        assert lease.is_active is False


# ---------------------------------------------------------------------------
# Admin View Integration Tests (HTTP-level)
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_client():
    """Return a Django test client logged in as a superuser."""
    user = User.objects.create_superuser(
        username="admin-test",
        password="admin-test-pw",
        email="admin-test@example.com",
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture()
def sample_plan():
    return MembershipPlan.objects.create(
        name="View Test Plan",
        monthly_price=Decimal("100.00"),
    )


@pytest.fixture()
def sample_member(sample_plan):
    return Member.objects.create(
        full_legal_name="View Test Member",
        email="viewtest@example.com",
        membership_plan=sample_plan,
        join_date=date(2024, 6, 1),
    )


@pytest.fixture()
def sample_space():
    return Space.objects.create(
        space_id="VT-001",
        space_type="studio",
        status="available",
    )


@pytest.fixture()
def sample_lease(sample_member, sample_space):
    return Lease.objects.create(
        member=sample_member,
        space=sample_space,
        lease_type="month_to_month",
        base_price=Decimal("300.00"),
        monthly_rent=Decimal("300.00"),
        start_date=date(2024, 6, 1),
    )


@pytest.mark.django_db
def describe_admin_membership_plan_views():
    def it_loads_changelist(admin_client):
        resp = admin_client.get("/admin/membership/membershipplan/")
        assert resp.status_code == 200

    def it_loads_add_form(admin_client):
        resp = admin_client.get("/admin/membership/membershipplan/add/")
        assert resp.status_code == 200

    def it_loads_change_form(admin_client, sample_plan):
        resp = admin_client.get(f"/admin/membership/membershipplan/{sample_plan.pk}/change/")
        assert resp.status_code == 200

    def it_creates_via_post(admin_client):
        resp = admin_client.post(
            "/admin/membership/membershipplan/add/",
            {
                "name": "POST Created Plan",
                "monthly_price": "150.00",
                "notes": "",
            },
        )
        assert resp.status_code == 302
        assert MembershipPlan.objects.filter(name="POST Created Plan").exists()


@pytest.mark.django_db
def describe_admin_member_views():
    def it_loads_changelist(admin_client, sample_member):
        resp = admin_client.get("/admin/membership/member/")
        assert resp.status_code == 200

    def it_loads_add_form(admin_client, sample_plan):
        resp = admin_client.get("/admin/membership/member/add/")
        assert resp.status_code == 200

    def it_loads_change_form(admin_client, sample_member):
        resp = admin_client.get(f"/admin/membership/member/{sample_member.pk}/change/")
        assert resp.status_code == 200

    def it_creates_via_post(admin_client, sample_plan):
        resp = admin_client.post(
            "/admin/membership/member/add/",
            {
                "full_legal_name": "POST Created Member",
                "preferred_name": "",
                "email": "postcreated@example.com",
                "phone": "",
                "membership_plan": sample_plan.pk,
                "status": "active",
                "role": "standard",
                "join_date": "2024-06-15",
                "notes": "",
                "emergency_contact_name": "",
                "emergency_contact_phone": "",
                "emergency_contact_relationship": "",
                # Inline management form (required for inlines)
                "leases-TOTAL_FORMS": "0",
                "leases-INITIAL_FORMS": "0",
                "leases-MIN_NUM_FORMS": "0",
                "leases-MAX_NUM_FORMS": "1000",
            },
        )
        assert resp.status_code == 302
        assert Member.objects.filter(full_legal_name="POST Created Member").exists()


@pytest.mark.django_db
def describe_admin_space_views():
    def it_loads_changelist(admin_client, sample_space):
        resp = admin_client.get("/admin/membership/space/")
        assert resp.status_code == 200

    def it_loads_add_form(admin_client):
        resp = admin_client.get("/admin/membership/space/add/")
        assert resp.status_code == 200

    def it_loads_change_form(admin_client, sample_space):
        resp = admin_client.get(f"/admin/membership/space/{sample_space.pk}/change/")
        assert resp.status_code == 200

    def it_creates_via_post(admin_client):
        resp = admin_client.post(
            "/admin/membership/space/add/",
            {
                "space_id": "POST-S1",
                "name": "",
                "space_type": "studio",
                "status": "available",
                "floorplan_ref": "",
                "notes": "",
                # Inline management form (required for inlines)
                "leases-TOTAL_FORMS": "0",
                "leases-INITIAL_FORMS": "0",
                "leases-MIN_NUM_FORMS": "0",
                "leases-MAX_NUM_FORMS": "1000",
            },
        )
        assert resp.status_code == 302
        assert Space.objects.filter(space_id="POST-S1").exists()


@pytest.mark.django_db
def describe_admin_lease_views():
    def it_loads_changelist(admin_client, sample_lease):
        resp = admin_client.get("/admin/membership/lease/")
        assert resp.status_code == 200

    def it_loads_add_form(admin_client, sample_member, sample_space):
        resp = admin_client.get("/admin/membership/lease/add/")
        assert resp.status_code == 200

    def it_loads_change_form(admin_client, sample_lease):
        resp = admin_client.get(f"/admin/membership/lease/{sample_lease.pk}/change/")
        assert resp.status_code == 200

    def it_creates_via_post(admin_client, sample_member, sample_space):
        resp = admin_client.post(
            "/admin/membership/lease/add/",
            {
                "member": sample_member.pk,
                "space": sample_space.pk,
                "lease_type": "month_to_month",
                "base_price": "400.00",
                "monthly_rent": "400.00",
                "start_date": "2024-07-01",
                "notes": "",
            },
        )
        assert resp.status_code == 302
        assert Lease.objects.filter(base_price=Decimal("400.00")).exists()
