#
# Copyright © Michal Čihař <michal@weblate.org>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from weblate_web.models import Donation, process_payment
from weblate_web.payments.backends import FioBank
from weblate_web.payments.models import Payment
from weblate_web.utils import PAYMENTS_ORIGIN


class Command(BaseCommand):
    help = "processes pending payments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-date",
            default=None,
            help="Date for parsing bank statements",
        )

    def handle(self, *args, **options):
        if settings.FIO_TOKEN:
            with transaction.atomic():
                FioBank.fetch_payments(from_date=options["from_date"])
        with transaction.atomic():
            self.pending()
        self.active()

    @staticmethod
    def pending():
        # Process pending ones
        payments = Payment.objects.filter(
            customer__origin=PAYMENTS_ORIGIN, state=Payment.ACCEPTED
        ).select_for_update()
        for payment in payments:
            process_payment(payment)

    @staticmethod
    def active():
        # Adjust active flag
        Donation.objects.filter(active=True, expires__lt=timezone.now()).update(
            active=False
        )
