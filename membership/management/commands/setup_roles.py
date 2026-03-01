from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


# Map role names to their permission codenames
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "super-admin": [],  # Gets all permissions
    "guild-manager": [
        "view_guild", "change_guild", "add_guild", "delete_guild",
        "view_guildmembership", "change_guildmembership", "add_guildmembership", "delete_guildmembership",
        "view_guilddocument", "change_guilddocument", "add_guilddocument", "delete_guilddocument",
        "view_guildwishlistitem", "change_guildwishlistitem", "add_guildwishlistitem", "delete_guildwishlistitem",
        "view_guildvote", "change_guildvote",
        "view_tool", "change_tool", "add_tool", "delete_tool",
    ],
    "class-manager": [
        "view_makerclass", "change_makerclass", "add_makerclass", "delete_makerclass",
        "view_classsession", "change_classsession", "add_classsession", "delete_classsession",
        "view_classimage", "change_classimage", "add_classimage", "delete_classimage",
        "view_classdiscountcode", "change_classdiscountcode", "add_classdiscountcode", "delete_classdiscountcode",
        "view_student", "change_student", "add_student", "delete_student",
    ],
    "orientation-manager": [
        "view_orientation", "change_orientation", "add_orientation", "delete_orientation",
        "view_scheduledorientation", "change_scheduledorientation", "add_scheduledorientation", "delete_scheduledorientation",
    ],
    "accountant": [
        "view_order", "change_order",
        "view_invoice", "change_invoice",
        "view_payout", "change_payout", "add_payout",
        "view_revenuesplit", "change_revenuesplit", "add_revenuesplit",
        "view_subscriptionplan", "view_membersubscription",
    ],
    "tour-guide": [
        "view_lead", "change_lead",
        "view_tour", "change_tour", "add_tour",
    ],
    "membership-manager": [
        "view_member", "change_member", "add_member",
        "view_membershipplan", "change_membershipplan",
        "view_space", "change_space",
        "view_lease", "change_lease", "add_lease", "delete_lease",
        "view_memberschedule", "change_memberschedule",
        "view_scheduleblock", "change_scheduleblock", "add_scheduleblock", "delete_scheduleblock",
    ],
    "guild-lead": [
        "view_guild", "change_guild",
        "view_guildmembership", "change_guildmembership", "add_guildmembership",
        "view_guilddocument", "change_guilddocument", "add_guilddocument",
        "view_guildwishlistitem", "change_guildwishlistitem", "add_guildwishlistitem",
        "view_tool", "change_tool",
    ],
    "orienter": [
        "view_orientation",
        "view_scheduledorientation", "change_scheduledorientation",
    ],
    "teacher": [
        "view_makerclass",
        "view_classsession",
        "view_student", "change_student",
    ],
}


class Command(BaseCommand):
    help = "Create permission groups and assign permissions for all roles"

    def handle(self, *args: object, **options: object) -> None:
        all_permissions = Permission.objects.all()

        for role_name, perm_codenames in ROLE_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=role_name)
            action = "Created" if created else "Updated"

            if role_name == "super-admin":
                group.permissions.set(all_permissions)
            else:
                perms = Permission.objects.filter(codename__in=perm_codenames)
                group.permissions.set(perms)

            self.stdout.write(
                self.style.SUCCESS(f"{action} group '{role_name}' with {group.permissions.count()} permissions")
            )
