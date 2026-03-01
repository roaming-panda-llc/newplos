"""BDD-style tests for the setup_roles management command."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def describe_setup_roles_command():
    def it_creates_all_ten_groups():
        call_command("setup_roles")
        assert Group.objects.count() == 10

    def it_creates_super_admin_group():
        call_command("setup_roles")
        group = Group.objects.get(name="super-admin")
        assert group.permissions.count() == Permission.objects.count()

    def it_creates_guild_manager_group():
        call_command("setup_roles")
        group = Group.objects.get(name="guild-manager")
        assert group.permissions.count() > 0
        assert group.permissions.filter(codename="change_guild").exists()

    def it_creates_class_manager_group():
        call_command("setup_roles")
        group = Group.objects.get(name="class-manager")
        assert group.permissions.filter(codename="add_makerclass").exists()

    def it_creates_orientation_manager_group():
        call_command("setup_roles")
        group = Group.objects.get(name="orientation-manager")
        assert group.permissions.filter(codename="change_orientation").exists()

    def it_creates_accountant_group():
        call_command("setup_roles")
        group = Group.objects.get(name="accountant")
        assert group.permissions.filter(codename="view_order").exists()

    def it_creates_tour_guide_group():
        call_command("setup_roles")
        group = Group.objects.get(name="tour-guide")
        assert group.permissions.filter(codename="change_tour").exists()

    def it_creates_membership_manager_group():
        call_command("setup_roles")
        group = Group.objects.get(name="membership-manager")
        assert group.permissions.filter(codename="change_member").exists()

    def it_creates_guild_lead_group():
        call_command("setup_roles")
        group = Group.objects.get(name="guild-lead")
        assert group.permissions.filter(codename="change_guild").exists()
        # guild-lead should NOT have delete_guild
        assert not group.permissions.filter(codename="delete_guild").exists()

    def it_creates_orienter_group():
        call_command("setup_roles")
        group = Group.objects.get(name="orienter")
        assert group.permissions.filter(codename="view_orientation").exists()
        assert group.permissions.filter(codename="change_scheduledorientation").exists()

    def it_creates_teacher_group():
        call_command("setup_roles")
        group = Group.objects.get(name="teacher")
        assert group.permissions.filter(codename="view_makerclass").exists()
        assert group.permissions.filter(codename="change_student").exists()

    def it_is_idempotent():
        call_command("setup_roles")
        call_command("setup_roles")
        assert Group.objects.count() == 10
