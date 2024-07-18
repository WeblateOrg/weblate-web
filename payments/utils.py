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

"""
Helper functions and classees from Weblate.

The code here is copy of code from Weblate, taken from
weblate/utils/validators.py and weblate/utils/fields.py.
"""

from __future__ import annotations

import os.path
import re
from email.mime.image import MIMEImage
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email as validate_email_django
from django.template.loader import render_to_string
from django.utils.translation import get_language, get_language_bidi
from django.utils.translation import gettext as _
from html2text import HTML2Text

if TYPE_CHECKING:
    from collections.abc import Iterable

# Reject some suspicious e-mail addresses, based on checks enforced by Exim MTA
EMAIL_BLACKLIST = re.compile(r"^([./|]|.*([@%!`#&?]|/\.\./))")


def validate_email(value):
    try:
        validate_email_django(value)
    except ValidationError:
        raise ValidationError(_("Enter a valid e-mail address."))
    user_part = value.rsplit("@", 1)[0]
    if EMAIL_BLACKLIST.match(user_part):
        raise ValidationError(_("Enter a valid e-mail address."))


def send_notification(notification: str, recipients: Iterable[str], **kwargs):
    if not recipients:
        return

    # HTML to text conversion
    html2text = HTML2Text(bodywidth=78)
    html2text.unicode_snob = True
    html2text.ignore_images = True
    html2text.pad_tables = True

    # Logos
    images = []
    for name in ("email-logo.png", "email-logo-footer.png"):
        filename = os.path.join(settings.STATIC_ROOT, name)
        with open(filename, "rb") as handle:
            image = MIMEImage(handle.read())
        image.add_header("Content-ID", f"<{name}@cid.weblate.org>")
        image.add_header("Content-Disposition", "inline", filename=name)
        images.append(image)

    # Context and subject
    context = {
        "LANGUAGE_CODE": get_language(),
        "LANGUAGE_BIDI": get_language_bidi(),
    }
    context.update(kwargs)
    subject = render_to_string(f"mail/{notification}_subject.txt", context).strip()
    context["subject"] = subject

    # Render body
    body = render_to_string(f"mail/{notification}.html", context).strip()

    # Prepare e-mail
    email = EmailMultiAlternatives(
        subject,
        html2text.handle(body),
        "billing@weblate.org",
        recipients,
    )
    email.mixed_subtype = "related"
    for image in images:
        email.attach(image)
    email.attach_alternative(body, "text/html")
    # Include invoice PDF if exists
    if "invoice" in kwargs:
        with open(kwargs["invoice"].pdf_path, "rb") as handle:
            email.attach(
                os.path.basename(kwargs["invoice"].pdf_path),
                handle.read(),
                "application/pdf",
            )
    email.send()
