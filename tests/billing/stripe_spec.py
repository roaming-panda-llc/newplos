"""Tests for stripe_utils and the bill_tabs management command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import stripe as stripe_lib
from django.core.management import call_command
from django.utils import timezone

from billing.models import Invoice, Order
from billing.stripe_utils import _create_local_invoice, create_invoice_for_user, get_stripe_key
from tests.billing.factories import OrderFactory
from tests.core.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# get_stripe_key
# ---------------------------------------------------------------------------


def describe_get_stripe_key():
    def it_returns_test_key_when_not_live_mode(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = "sk_test_abc123"
        settings.STRIPE_LIVE_SECRET_KEY = "sk_live_xyz789"

        assert get_stripe_key() == "sk_test_abc123"

    def it_returns_live_key_when_live_mode(settings):
        settings.STRIPE_LIVE_MODE = True
        settings.STRIPE_TEST_SECRET_KEY = "sk_test_abc123"
        settings.STRIPE_LIVE_SECRET_KEY = "sk_live_xyz789"

        assert get_stripe_key() == "sk_live_xyz789"

    def it_returns_empty_string_when_no_key_configured(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        assert get_stripe_key() == ""


# ---------------------------------------------------------------------------
# _create_local_invoice
# ---------------------------------------------------------------------------


def describe_create_local_invoice():
    def it_creates_an_invoice_record():
        user = UserFactory()
        orders = Order.objects.filter(pk__in=[OrderFactory(user=user).pk, OrderFactory(user=user).pk])

        invoice = _create_local_invoice(user, orders)

        assert invoice.pk is not None
        assert Invoice.objects.filter(pk=invoice.pk).exists()

    def it_calculates_total_from_orders():
        user = UserFactory()
        o1 = OrderFactory(user=user, amount=3000)
        o2 = OrderFactory(user=user, amount=7000)
        orders = Order.objects.filter(pk__in=[o1.pk, o2.pk])

        invoice = _create_local_invoice(user, orders)

        assert invoice.amount_due == 10000

    def it_stores_line_items():
        user = UserFactory()
        order = OrderFactory(user=user, description="Monthly dues", amount=5000)
        orders = Order.objects.filter(pk=order.pk)

        invoice = _create_local_invoice(user, orders)

        assert invoice.line_items == [{"description": "Monthly dues", "amount": 5000}]

    def it_sets_status_to_open():
        user = UserFactory()
        order = OrderFactory(user=user)
        orders = Order.objects.filter(pk=order.pk)

        invoice = _create_local_invoice(user, orders)

        assert invoice.status == "open"

    def it_links_invoice_to_user():
        user = UserFactory()
        order = OrderFactory(user=user)
        orders = Order.objects.filter(pk=order.pk)

        invoice = _create_local_invoice(user, orders)

        assert invoice.user == user

    def it_does_not_set_stripe_invoice_id():
        user = UserFactory()
        order = OrderFactory(user=user)
        orders = Order.objects.filter(pk=order.pk)

        invoice = _create_local_invoice(user, orders)

        assert invoice.stripe_invoice_id == ""


# ---------------------------------------------------------------------------
# create_invoice_for_user
# ---------------------------------------------------------------------------


def describe_create_invoice_for_user():
    def it_falls_back_to_local_invoice_when_no_api_key(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        user = UserFactory()
        order = OrderFactory(user=user, amount=4000)
        orders = Order.objects.filter(pk=order.pk)

        invoice = create_invoice_for_user(user, orders)

        assert invoice is not None
        assert invoice.stripe_invoice_id == ""
        assert invoice.amount_due == 4000

    def it_returns_none_on_stripe_error(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = "sk_test_fakekeyfortesting"

        user = UserFactory()
        order = OrderFactory(user=user, amount=2000)
        orders = Order.objects.filter(pk=order.pk)

        with patch("billing.stripe_utils.stripe.Customer") as mock_customer:
            mock_customer.list.side_effect = stripe_lib.StripeError("API error")
            result = create_invoice_for_user(user, orders)

        assert result is None

    def it_creates_stripe_invoice_when_api_key_present(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = "sk_test_fakekeyfortesting"

        user = UserFactory()
        order = OrderFactory(user=user, amount=5000)
        orders = Order.objects.filter(pk=order.pk)

        mock_customer = MagicMock()
        mock_customer.id = "cus_test123"

        mock_stripe_invoice = MagicMock()
        mock_stripe_invoice.id = "in_test456"
        mock_stripe_invoice.invoice_pdf = "https://stripe.com/invoice.pdf"

        with (
            patch("billing.stripe_utils.stripe.Customer") as mock_cust_cls,
            patch("billing.stripe_utils.stripe.InvoiceItem") as mock_item_cls,
            patch("billing.stripe_utils.stripe.Invoice") as mock_inv_cls,
        ):
            mock_cust_cls.list.return_value.data = [mock_customer]
            mock_inv_cls.create.return_value = mock_stripe_invoice
            mock_inv_cls.finalize_invoice.return_value = mock_stripe_invoice

            invoice = create_invoice_for_user(user, orders)

        assert invoice is not None
        assert invoice.stripe_invoice_id == "in_test456"
        assert invoice.amount_due == 5000
        assert invoice.pdf_url == "https://stripe.com/invoice.pdf"


# ---------------------------------------------------------------------------
# bill_tabs management command
# ---------------------------------------------------------------------------


def describe_bill_tabs_command():
    def it_does_nothing_when_no_tabs_exist(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        out = StringIO()
        call_command("bill_tabs", stdout=out)

        assert "No outstanding tabs" in out.getvalue()

    def it_bills_user_with_on_tab_orders(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        user = UserFactory()
        OrderFactory(user=user, status="on_tab", amount=3000)

        out = StringIO()
        call_command("bill_tabs", stdout=out)

        assert Invoice.objects.filter(user=user).exists()

    def it_updates_order_status_to_billed(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        user = UserFactory()
        order = OrderFactory(user=user, status="on_tab", amount=5000)

        call_command("bill_tabs", stdout=StringIO())

        order.refresh_from_db()
        assert order.status == Order.Status.BILLED

    def it_sets_billed_at_timestamp(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        before = timezone.now()
        user = UserFactory()
        order = OrderFactory(user=user, status="on_tab", amount=5000)

        call_command("bill_tabs", stdout=StringIO())

        order.refresh_from_db()
        assert order.billed_at is not None
        assert order.billed_at >= before

    def it_handles_multiple_users(settings):
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        user_a = UserFactory()
        user_b = UserFactory()
        OrderFactory(user=user_a, status="on_tab", amount=1000)
        OrderFactory(user=user_b, status="on_tab", amount=2000)

        out = StringIO()
        call_command("bill_tabs", stdout=out)

        assert Invoice.objects.filter(user=user_a).exists()
        assert Invoice.objects.filter(user=user_b).exists()
        assert "2 users total" in out.getvalue()

    def it_is_idempotent_second_run_finds_no_tabs(settings):
        """Running twice does not double-bill: first run bills orders, second run finds none."""
        settings.STRIPE_LIVE_MODE = False
        settings.STRIPE_TEST_SECRET_KEY = ""

        user = UserFactory()
        OrderFactory(user=user, status="on_tab", amount=5000)

        call_command("bill_tabs", stdout=StringIO())
        invoice_count_after_first = Invoice.objects.filter(user=user).count()

        out = StringIO()
        call_command("bill_tabs", stdout=out)
        invoice_count_after_second = Invoice.objects.filter(user=user).count()

        assert invoice_count_after_first == 1
        assert invoice_count_after_second == 1
        assert "No outstanding tabs" in out.getvalue()
