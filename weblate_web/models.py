#
# Copyright © 2012–2021 Michal Čihař <michal@cihar.com>
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

from datetime import timedelta
from uuid import uuid4

import html2text
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import override, ugettext_lazy
from markupfield.fields import MarkupField
from paramiko.client import SSHClient

from payments.models import Payment, get_period_delta
from payments.utils import send_notification

PAYMENTS_ORIGIN = "https://weblate.org/donate/process/"

REWARDS = (
    (0, ugettext_lazy("No reward")),
    (1, ugettext_lazy("Name in the list of supporters")),
    (2, ugettext_lazy("Link in the list of supporters")),
    (3, ugettext_lazy("Logo and link on the Weblate website")),
)

TOPICS = (
    ("release", ugettext_lazy("Release")),
    ("feature", ugettext_lazy("Features")),
    ("announce", ugettext_lazy("Announcement")),
    ("conferences", ugettext_lazy("Conferences")),
    ("hosting", ugettext_lazy("Hosted Weblate")),
    ("development", ugettext_lazy("Development")),
    ("localization", ugettext_lazy("Localization")),
)

TOPIC_DICT = dict(TOPICS)


def create_backup_repository(service):
    """
    Configure backup repository.

    - create filesystem folders
    - store ssh key
    - create subaccount
    """
    # Create folder and SSH key
    client = SSHClient()
    client.load_system_host_keys()
    client.connect(**settings.STORAGE_SERVER)
    ftp = client.open_sftp()
    dirname = str(uuid4())
    ftp.mkdir(dirname)
    ftp.chdir(dirname)
    ftp.mkdir(".ssh")
    ftp.chdir(".ssh")
    with ftp.open("authorized_keys", "w") as handle:
        handle.write(service.last_report.ssh_key)

    # Create account on the service
    url = "https://robot-ws.your-server.de/storagebox/{}/subaccount".format(
        settings.STORAGE_BOX
    )
    response = requests.post(
        url,
        data={
            "homedirectory": f"weblate/{dirname}",
            "ssh": "1",
            "external_reachability": "1",
            "comment": f"Weblate backup service {service.pk}",
        },
        auth=(settings.STORAGE_USER, settings.STORAGE_PASSWORD),
    )
    data = response.json()
    return "ssh://{}@{}:23/./backups".format(
        data["subaccount"]["username"], data["subaccount"]["server"]
    )


class Donation(models.Model):
    user = models.ForeignKey(User, on_delete=models.deletion.CASCADE)
    payment = models.UUIDField(blank=True, null=True)  # noqa: DJ01
    reward = models.IntegerField(choices=REWARDS, default=0)
    link_text = models.CharField(
        verbose_name=ugettext_lazy("Link text"), max_length=200, blank=True
    )
    link_url = models.URLField(verbose_name=ugettext_lazy("Link URL"), blank=True)
    link_image = models.ImageField(
        verbose_name=ugettext_lazy("Link image"), blank=True, upload_to="donations/"
    )
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField()
    active = models.BooleanField(blank=True, db_index=True)

    class Meta:
        verbose_name = "Donation"
        verbose_name_plural = "Donations"

    def __str__(self):
        return f"{self.user}:{self.reward}"

    def get_absolute_url(self):
        return reverse("donate-edit", kwargs={"pk": self.pk})

    @cached_property
    def payment_obj(self):
        if not self.payment:
            return None
        return Payment.objects.get(pk=self.payment)

    def list_payments(self):
        past = set(self.pastpayments_set.values_list("payment", flat=True))
        query = Q(pk=self.payment)
        if past:
            query |= Q(pk__in=past)
            query |= Q(repeat__pk__in=past)
        if self.payment:
            query |= Q(repeat__pk=self.payment)
        return Payment.objects.filter(query).distinct()

    def get_amount(self):
        if not self.payment:
            return 0
        return self.payment_obj.amount

    def get_payment_description(self):
        if self.reward:
            return f"Weblate donation: {self.get_reward_display()}"
        return "Weblate donation"

    def send_notification(self, notification):
        send_notification(
            notification,
            [self.user.email],
            donation=self,
        )


def process_donation(payment):
    if payment.state != Payment.ACCEPTED:
        raise ValueError("Can not process not accepted payment")
    if payment.repeat:
        # Update existing
        donation = Donation.objects.get(payment=payment.repeat.pk)
        payment.start = donation.expires
        donation.expires += get_period_delta(payment.repeat.recurring)
        payment.end = donation.expires
        donation.save()
    elif "donation" in payment.extra:
        donation = Donation.objects.get(pk=payment.extra["donation"])
        if donation.payment:
            donation.pastpayments_set.create(payment=donation.payment)
        payment.start = donation.expires
        donation.expires += get_period_delta(payment.recurring)
        payment.end = donation.expires
        donation.payment = payment.pk
        donation.save()
    else:
        user = User.objects.get(pk=payment.customer.user_id)
        reward = payment.extra.get("reward", 0)
        # Calculate expiry
        expires = timezone.now()
        if payment.recurring:
            payment.start = expires
            expires += get_period_delta(payment.recurring)
            payment.end = expires
        elif reward:
            payment.start = expires
            expires += get_period_delta("y")
            payment.end = expires
        # Create new
        donation = Donation.objects.create(
            user=user,
            payment=payment.pk,
            reward=int(reward),
            expires=expires,
            active=True,
        )
    # Flag payment as processed
    payment.state = Payment.PROCESSED
    payment.save()
    return donation


def get_service(payment, user):
    try:
        return user.service_set.get(pk=payment.extra["service"])
    except Service.DoesNotExist:
        try:
            return user.service_set.get()
        except (Service.MultipleObjectsReturned, Service.DoesNotExist):
            service = user.service_set.create()
            service.was_created = True
            return service


def process_subscription(payment):
    if payment.state != Payment.ACCEPTED:
        raise ValueError("Can not process not accepted payment")
    if payment.repeat:
        # Update existing
        subscription = Subscription.objects.get(payment=payment.repeat.pk)
        payment.start = subscription.expires
        subscription.expires += get_period_delta(payment.repeat.recurring)
        payment.end = subscription.expires
        subscription.save()
    elif isinstance(payment.extra["subscription"], int):
        subscription = Subscription.objects.get(pk=payment.extra["subscription"])
        if subscription.payment:
            subscription.pastpayments_set.create(payment=subscription.payment)
        payment.start = subscription.expires
        subscription.expires += get_period_delta(subscription.get_repeat())
        payment.end = subscription.expires
        subscription.payment = payment.pk
        subscription.save()
    else:
        user = User.objects.get(pk=payment.customer.user_id)
        package = Package.objects.get(name=payment.extra["subscription"])
        # Calculate expiry
        repeat = package.get_repeat()
        if repeat:
            expires = timezone.now()
            payment.start = expires
            expires += get_period_delta(repeat)
            payment.end = expires
        else:
            expires = timezone.now()
        # Create new
        service = get_service(payment, user)
        subscription = Subscription.objects.create(
            service=service,
            payment=payment.pk,
            package=package.name,
            expires=expires,
        )
        with override("en"):
            send_notification(
                "new_subscription",
                settings.NOTIFY_SUBSCRIPTION,
                subscription=subscription,
                service=subscription.service,
            )
        if service.was_created and service.needs_token:
            subscription.send_notification("subscription_intro")
    # Flag payment as processed
    payment.state = Payment.PROCESSED
    payment.save()
    return subscription


class Image(models.Model):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(
        upload_to="images/", help_text="Article image, 1200x630 pixels"
    )

    class Meta:
        verbose_name = "Image"
        verbose_name_plural = "Images"

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    timestamp = models.DateTimeField(db_index=True)
    author = models.ForeignKey(
        User, editable=False, on_delete=models.deletion.SET_NULL, null=True
    )
    topic = models.CharField(max_length=100, db_index=True, choices=TOPICS, default="")
    body = MarkupField(default_markup_type="markdown")
    summary = models.TextField(
        blank=True, help_text="Will be generated from first body paragraph if empty"
    )
    image = models.ForeignKey(
        Image, on_delete=models.deletion.SET_NULL, blank=True, null=True
    )
    milestone = models.BooleanField(
        blank=True,
        db_index=True,
        default=False,
        help_text="This is an important milestone, shown on milestones archive",
    )

    class Meta:
        verbose_name = "Blog post"
        verbose_name_plural = "Blog posts"

    def __str__(self):
        return self.title

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        # Need to save first as rendered value is available only then
        super().save(force_insert, force_update, using, update_fields)
        if not self.summary:
            h2t = html2text.HTML2Text()
            h2t.body_width = 0
            h2t.ignore_images = True
            h2t.ignore_links = True
            h2t.ignore_emphasis = True
            text = h2t.handle(self.body.rendered)  # pylint: disable=no-member
            self.summary = text.splitlines()[0]
            if self.summary:
                super().save(update_fields=["summary"])

    def get_absolute_url(self):
        return reverse("post", kwargs={"slug": self.slug})


def generate_secret():
    return get_random_string(64)


class Package(models.Model):
    name = models.CharField(max_length=150, unique=True)
    verbose = models.CharField(max_length=400)
    price = models.IntegerField()
    limit_projects = models.IntegerField(default=0)
    limit_languages = models.IntegerField(default=0)
    limit_source_strings = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Service package"
        verbose_name_plural = "Service packages"

    def __str__(self):
        return self.verbose

    def get_repeat(self):
        if self.name in ("basic", "extended", "premium", "backup"):
            return "y"
        if self.name.startswith("hosted:") or self.name.startswith("shared:"):
            if self.name.endswith("-m"):
                return "m"
            return "y"
        return ""


class Service(models.Model):
    secret = models.CharField(max_length=100, default=generate_secret, db_index=True)
    users = models.ManyToManyField(User)
    status = models.CharField(
        max_length=150,
        choices=(
            ("community", ugettext_lazy("Expired service")),
            ("hosted", ugettext_lazy("Dedicated hosted service")),
            ("shared", ugettext_lazy("Hosted service")),
            ("basic", ugettext_lazy("Basic self-hosted support")),
            ("extended", ugettext_lazy("Extended self-hosted support")),
            ("premium", ugettext_lazy("Premium self-hosted support")),
        ),
        default="community",
    )
    backup_repository = models.CharField(max_length=500, default="", blank=True)
    limit_languages = models.IntegerField(default=0)
    limit_projects = models.IntegerField(default=0)
    limit_source_strings = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    hosted_billing = models.IntegerField(default=0, db_index=True)

    class Meta:
        verbose_name = "Customer service"
        verbose_name_plural = "Customer services"

    def __str__(self):
        if self.last_report:
            url = self.last_report.site_url
        else:
            url = ""
        return f"{self.get_status_display()}: {self.user_emails}: {url}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.was_created = False

    @property
    def needs_token(self):
        return self.status not in ("hosted", "shared", "community")

    @cached_property
    def site_title(self):
        if self.last_report:
            return self.last_report.site_title
        return "Weblate"

    @cached_property
    def site_url(self):
        if self.last_report:
            return self.last_report.site_url
        return ""

    @cached_property
    def site_version(self):
        if self.last_report:
            return self.last_report.version
        return ""

    def projects_limit(self):
        report = self.last_report
        if report:
            if self.limit_projects:
                return f"{report.projects}/{self.limit_projects}"
            return f"{report.projects}"
        return "0"

    projects_limit.short_description = "Projects"

    def languages_limit(self):
        report = self.last_report
        if report:
            if self.limit_languages:
                return f"{report.languages}/{self.limit_languages}"
            return f"{report.languages}"
        return "0"

    languages_limit.short_description = "Languages"

    def source_strings_limit(self):
        report = self.last_report
        if report:
            if self.limit_source_strings:
                return f"{report.source_strings}/{self.limit_source_strings}"
            return f"{report.source_strings}"
        return "0"

    source_strings_limit.short_description = "Source strings"

    @cached_property
    def user_emails(self):
        return ", ".join(self.users.values_list("email", flat=True))

    @cached_property
    def last_report(self):
        try:
            return self.report_set.latest("timestamp")
        except Report.DoesNotExist:
            return None

    @cached_property
    def hosted_subscriptions(self):
        return self.subscription_set.filter(package__startswith="hosted:")

    @cached_property
    def shared_subscriptions(self):
        return self.subscription_set.filter(package__startswith="shared:")

    @cached_property
    def basic_subscriptions(self):
        return self.subscription_set.filter(package="basic")

    @cached_property
    def extended_subscriptions(self):
        return self.subscription_set.filter(package="extended")

    @cached_property
    def premium_subscriptions(self):
        return self.subscription_set.filter(package="premium")

    @cached_property
    def support_subscriptions(self):
        return (
            self.hosted_subscriptions
            | self.shared_subscriptions
            | self.basic_subscriptions
            | self.extended_subscriptions
            | self.premium_subscriptions
        )

    @cached_property
    def backup_subscriptions(self):
        return self.subscription_set.filter(package="backup")

    @cached_property
    def expires(self):
        try:
            return self.support_subscriptions.latest("expires").expires
        except Subscription.DoesNotExist:
            return timezone.now()

    def get_suggestions(self):
        if not self.support_subscriptions.exists():
            yield (
                "basic",
                _("Basic support"),
                _("Never get hold back by a problem."),
                _("Set priority for all your questions and reported bugs."),
                "img/Support-Basic.svg",
                _("Get your support"),
            )

        if (
            not self.hosted_subscriptions.exists()
            and not self.shared_subscriptions.exists()
        ):
            if not self.premium_subscriptions.exists():
                yield (
                    "premium",
                    _("Premium support"),
                    _("Don’t be waiting with your work paused."),
                    _("This guarantees you the answers the NBD at the latest."),
                    "img/Support-Premium.svg",
                    _("Become Premium"),
                )

            if not self.extended_subscriptions.exists():
                yield (
                    "extended",
                    _("Extended support"),
                    _("Don’t be Basic, get a worry-free package."),
                    _("We will manage upgrades for you."),
                    "img/Support-Plus.svg",
                    _("Stay updated and supported"),
                )

            if not self.backup_subscriptions.exists():
                yield (
                    "backup",
                    _("Backup service"),
                    _("Easily put your backups in a safe place."),
                    _("Encrypted and automatic backups, always available."),
                    "img/Support-Backup.svg",
                    _("Backup daily"),
                )

    def update_status(self):
        status = "community"
        package = "community"
        if self.hosted_subscriptions.filter(expires__gt=timezone.now()).exists():
            status = "hosted"
            package = self.hosted_subscriptions.latest("expires").package
        elif self.shared_subscriptions.filter(expires__gt=timezone.now()).exists():
            status = "shared"
            package = self.shared_subscriptions.latest("expires").package
        elif self.premium_subscriptions.filter(expires__gt=timezone.now()).exists():
            status = "premium"
        elif self.extended_subscriptions.filter(expires__gt=timezone.now()).exists():
            status = "extended"
        elif self.basic_subscriptions.filter(expires__gt=timezone.now()).exists():
            status = "basic"
        package_obj = Package.objects.get(name=package)

        if (
            status != self.status
            or package_obj.limit_source_strings != self.limit_source_strings
        ):
            self.status = status
            self.limit_source_strings = package_obj.limit_source_strings
            self.limit_languages = package_obj.limit_languages
            self.limit_projects = package_obj.limit_projects
            self.save()

    def create_backup(self):
        backup = False
        if self.hosted_subscriptions.filter(expires__gt=timezone.now()).exists():
            backup = True
        if self.backup_subscriptions.filter(expires__gt=timezone.now()).exists():
            backup = True
        if backup and not self.backup_repository and self.report_set.exists():
            self.backup_repository = create_backup_repository(self)
            self.save(update_fields=["backup_repository"])

    def check_in_limits(self):
        if (
            self.limit_source_strings
            and self.last_report.source_strings > self.limit_source_strings
        ):
            return False
        if self.limit_projects and self.last_report.projects > self.limit_projects:
            return False
        if self.limit_languages and self.last_report.languages > self.limit_languages:
            return False
        return True

    def regenerate(self):
        self.secret = generate_secret()
        self.save(update_fields=["secret"])


class Subscription(models.Model):
    service = models.ForeignKey(Service, on_delete=models.deletion.CASCADE)
    payment = models.UUIDField(blank=True, null=True)  # noqa: DJ01
    package = models.CharField(max_length=150)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField()

    class Meta:
        verbose_name = "Customer’s subscription"
        verbose_name_plural = "Customer’s subscriptions"

    def __str__(self):
        return f"{self.get_package_display()}: {self.service}"

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        super().save(force_insert, force_update, using, update_fields)
        self.service.update_status()

    def get_absolute_url(self):
        return reverse("subscription-view", kwargs={"pk": self.pk})

    @cached_property
    def yearly_package(self):
        if self.package.endswith("-m"):
            return self.package[:-2]
        return None

    @cached_property
    def package_obj(self):
        return Package.objects.get(name=self.package)

    def get_package_display(self):
        return _(self.package_obj.verbose)

    def get_repeat(self):
        return self.package_obj.get_repeat()

    def active(self):
        return self.expires >= timezone.now()

    def get_amount(self):
        return self.package_obj.price

    @cached_property
    def payment_obj(self):
        return Payment.objects.get(pk=self.payment)

    def list_payments(self):
        # pylint: disable=no-member
        past = set(self.pastpayments_set.values_list("payment", flat=True))
        query = Q(pk=self.payment)
        if past:
            query |= Q(pk__in=past)
            query |= Q(repeat__pk__in=past)
        if self.payment:
            query |= Q(repeat__pk=self.payment)
        return Payment.objects.filter(query).distinct()

    def send_notification(self, notification):
        send_notification(
            notification,
            [user.email for user in self.service.users.all()],
            subscription=self,
        )
        with override("en"):
            send_notification(
                notification,
                settings.NOTIFY_SUBSCRIPTION,
                subscription=self,
            )

    def could_be_obsolete(self):
        expires = timezone.now() + timedelta(days=3)
        return (
            self.package in ("basic", "extended", "premium")
            and self.service.support_subscriptions.exclude(pk=self.pk)
            .filter(expires__gt=expires)
            .exists()
        )


class PastPayments(models.Model):
    subscription = models.ForeignKey(
        Subscription, on_delete=models.deletion.CASCADE, null=True, blank=True
    )
    donation = models.ForeignKey(
        Donation, on_delete=models.deletion.CASCADE, null=True, blank=True
    )
    payment = models.UUIDField()

    class Meta:
        verbose_name = "Past payment"
        verbose_name_plural = "Past payments"

    def __str__(self):
        return f"{self.subscription}: {self.payment}"


class Report(models.Model):
    service = models.ForeignKey(Service, on_delete=models.deletion.CASCADE)
    site_url = models.URLField(default="")
    site_title = models.TextField(default="")
    version = models.TextField(default="")
    ssh_key = models.TextField(default="")
    users = models.IntegerField(default=0)
    projects = models.IntegerField(default=0)
    components = models.IntegerField(default=0)
    languages = models.IntegerField(default=0)
    source_strings = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Weblate report"
        verbose_name_plural = "Weblate reports"

    def __str__(self):
        return self.site_url
