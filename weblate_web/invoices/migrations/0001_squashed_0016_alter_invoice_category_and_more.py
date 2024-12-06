# Generated by Django 5.1.3 on 2024-12-06 19:56

import datetime
import uuid

import django.core.serializers.json
import django.core.validators
import django.db.models.deletion
import django.db.models.expressions
import django.db.models.functions.comparison
import django.db.models.functions.datetime
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    replaces = [
        ("invoices", "0001_initial"),
        ("invoices", "0002_alter_invoice_customer_alter_invoice_discount_and_more"),
        ("invoices", "0003_alter_invoice_kind"),
        ("invoices", "0004_invoice_number"),
        ("invoices", "0005_alter_invoice_currency_alter_invoice_number"),
        ("invoices", "0006_remove_invoice_number_alter_invoice_kind"),
        ("invoices", "0007_invoice_number"),
        ("invoices", "0008_invoice_category"),
        ("invoices", "0009_alter_invoice_kind"),
        ("invoices", "0010_remove_invoiceitem_invoice_delete_invoice_and_more"),
        ("invoices", "0011_invoice_invoiceitem_invoice_unique_number"),
        ("invoices", "0012_invoiceitem_package_alter_invoiceitem_description_and_more"),
        ("invoices", "0013_invoice_extra"),
        ("invoices", "0014_alter_invoice_currency"),
        ("invoices", "0015_invoiceitem_end_date_invoiceitem_start_date"),
        ("invoices", "0016_alter_invoice_category_and_more"),
    ]

    initial = True

    dependencies = [
        ("weblate_web", "0032_alter_donation_customer_alter_donation_user_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Discount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.CharField(max_length=200, unique=True)),
                (
                    "percents",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(99),
                        ]
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sequence", models.IntegerField(editable=False)),
                ("issue_date", models.DateField(default=datetime.date.today)),
                ("due_date", models.DateField(blank=True)),
                (
                    "kind",
                    models.IntegerField(
                        choices=[
                            (10, "Invoice"),
                            (20, "Proforma"),
                            (30, "Quote"),
                            (40, "Draft"),
                        ],
                        default=10,
                    ),
                ),
                ("customer_reference", models.CharField(blank=True, max_length=100)),
                ("vat_rate", models.IntegerField(default=0)),
                ("currency", models.IntegerField(choices=[(0, "EUR")], default=0)),
                (
                    "prepaid",
                    models.BooleanField(
                        default=False,
                        help_text="Invoices paid in advance (card payment, pro forma)",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="payments.customer",
                    ),
                ),
                (
                    "discount",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="invoices.discount",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="invoices.invoice",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InvoiceItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.CharField(max_length=200)),
                (
                    "quantity",
                    models.IntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(50),
                        ],
                    ),
                ),
                (
                    "quantity_unit",
                    models.IntegerField(choices=[(0, ""), (1, "hours")], default=0),
                ),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=7)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="invoices.invoice",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                django.db.models.functions.datetime.Extract("issue_date", "year"),
                models.F("kind"),
                models.F("sequence"),
                name="unique_number",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="payments.customer"
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="discount",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="invoices.discount",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="invoices.invoice",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="currency",
            field=models.IntegerField(choices=[(0, "EUR"), (1, "CZK")], default=0),
        ),
        migrations.AddField(
            model_name="invoice",
            name="number",
            field=models.GeneratedField(
                db_persist=True,
                expression=django.db.models.functions.text.Concat(
                    django.db.models.functions.text.LPad(
                        django.db.models.functions.comparison.Cast(
                            "kind", models.CharField()
                        ),
                        2,
                        models.Value("0"),
                    ),
                    django.db.models.functions.comparison.Cast(
                        django.db.models.expressions.CombinedExpression(
                            django.db.models.functions.datetime.Extract(
                                "issue_date", "year"
                            ),
                            "%%",
                            models.Value(2000),
                        ),
                        models.CharField(),
                    ),
                    django.db.models.functions.text.LPad(
                        django.db.models.functions.comparison.Cast(
                            "sequence", models.CharField()
                        ),
                        6,
                        models.Value("0"),
                    ),
                ),
                output_field=models.CharField(max_length=20),
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="category",
            field=models.IntegerField(
                choices=[
                    (1, "Hosting"),
                    (2, "Support"),
                    (3, "Development"),
                    (4, "Donation"),
                ],
                default=1,
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="kind",
            field=models.IntegerField(
                choices=[
                    (0, "Draft"),
                    (10, "Invoice"),
                    (50, "Pro Forma Invoice"),
                    (90, "Quote"),
                ]
            ),
        ),
        migrations.RemoveField(
            model_name="invoiceitem",
            name="invoice",
        ),
        migrations.DeleteModel(
            name="Invoice",
        ),
        migrations.DeleteModel(
            name="InvoiceItem",
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("sequence", models.IntegerField(editable=False)),
                (
                    "number",
                    models.GeneratedField(
                        db_persist=True,
                        expression=django.db.models.functions.text.Concat(
                            django.db.models.functions.text.LPad(
                                django.db.models.functions.comparison.Cast(
                                    "kind", models.CharField()
                                ),
                                2,
                                models.Value("0"),
                            ),
                            django.db.models.functions.comparison.Cast(
                                django.db.models.expressions.CombinedExpression(
                                    django.db.models.functions.datetime.Extract(
                                        "issue_date", "year"
                                    ),
                                    "%%",
                                    models.Value(2000),
                                ),
                                models.CharField(),
                            ),
                            django.db.models.functions.text.LPad(
                                django.db.models.functions.comparison.Cast(
                                    "sequence", models.CharField()
                                ),
                                6,
                                models.Value("0"),
                            ),
                        ),
                        output_field=models.CharField(max_length=20),
                        unique=True,
                    ),
                ),
                ("issue_date", models.DateField(default=datetime.date.today)),
                ("due_date", models.DateField(blank=True)),
                (
                    "kind",
                    models.IntegerField(
                        choices=[
                            (0, "Draft"),
                            (10, "Invoice"),
                            (50, "Pro Forma Invoice"),
                            (90, "Quote"),
                        ]
                    ),
                ),
                (
                    "category",
                    models.IntegerField(
                        choices=[
                            (1, "Hosting"),
                            (2, "Support"),
                            (3, "Development"),
                            (4, "Donation"),
                        ],
                        default=1,
                    ),
                ),
                ("customer_reference", models.CharField(blank=True, max_length=100)),
                ("vat_rate", models.IntegerField(default=0)),
                (
                    "currency",
                    models.IntegerField(choices=[(0, "EUR"), (1, "CZK")], default=0),
                ),
                (
                    "prepaid",
                    models.BooleanField(
                        default=False,
                        help_text="Invoices paid in advance (card payment, pro forma)",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="payments.customer",
                    ),
                ),
                (
                    "discount",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="invoices.discount",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="invoices.invoice",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InvoiceItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.CharField(max_length=200)),
                (
                    "quantity",
                    models.IntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(50),
                        ],
                    ),
                ),
                (
                    "quantity_unit",
                    models.IntegerField(choices=[(0, ""), (1, "hours")], default=0),
                ),
                ("unit_price", models.DecimalField(decimal_places=3, max_digits=8)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="invoices.invoice",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                models.F("sequence"),
                django.db.models.functions.datetime.Extract("issue_date", "year"),
                models.F("kind"),
                name="unique_number",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceitem",
            name="description",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name="invoiceitem",
            name="unit_price",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=8),
        ),
        migrations.AddField(
            model_name="invoice",
            name="extra",
            field=models.JSONField(
                blank=True,
                default=dict,
                encoder=django.core.serializers.json.DjangoJSONEncoder,
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="currency",
            field=models.IntegerField(
                choices=[(0, "EUR"), (1, "CZK"), (2, "USD"), (3, "GBP")], default=0
            ),
        ),
        migrations.AddField(
            model_name="invoiceitem",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoiceitem",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="category",
            field=models.IntegerField(
                choices=[
                    (1, "Hosting"),
                    (2, "Support"),
                    (3, "Development"),
                    (4, "Donation"),
                ],
                help_text="Helps to categorize income",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="customer_reference",
            field=models.CharField(
                blank=True,
                help_text="Text will be shown on the generated invoice",
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="discount",
            field=models.ForeignKey(
                blank=True,
                help_text="Automatically applied to all invoice items",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="invoices.discount",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="due_date",
            field=models.DateField(
                blank=True,
                help_text="Due date / Quote validity, keep blank unless specific terms are needed",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="number",
            field=models.GeneratedField(
                db_persist=True,
                expression=django.db.models.functions.text.Concat(
                    django.db.models.functions.text.LPad(
                        django.db.models.functions.comparison.Cast(
                            "kind", models.CharField()
                        ),
                        2,
                        models.Value("0"),
                    ),
                    django.db.models.functions.comparison.Cast(
                        django.db.models.expressions.CombinedExpression(
                            django.db.models.functions.datetime.Extract(
                                "issue_date", "year"
                            ),
                            "%%",
                            models.Value(2000),
                        ),
                        models.CharField(),
                    ),
                    django.db.models.functions.text.LPad(
                        django.db.models.functions.comparison.Cast(
                            "sequence", models.CharField()
                        ),
                        6,
                        models.Value("0"),
                    ),
                ),
                help_text="Invoice number is automatically generated",
                output_field=models.CharField(max_length=20),
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text="Invoices tracking, use for issuing invoice from quote",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="invoices.invoice",
                verbose_name="Parent invoice",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="prepaid",
            field=models.BooleanField(
                default=False,
                help_text="Invoices paid in advance (card payment, invoices issued after paying pro forma)",
                verbose_name="Already paid",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="vat_rate",
            field=models.IntegerField(
                default=0,
                help_text="VAT rate in percents to apply on the invoice",
                verbose_name="VAT rate",
            ),
        ),
        migrations.AddField(
            model_name="invoiceitem",
            name="package",
            field=models.ForeignKey(
                blank=True,
                help_text="Selecting package will automatically fill in description and price",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="weblate_web.package",
            ),
        ),
    ]
