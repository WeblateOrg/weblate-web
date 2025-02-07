# Generated by Django 5.1.2 on 2024-10-24 06:32

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invoices", "0011_invoice_invoiceitem_invoice_unique_number"),
        ("payments", "0034_remove_payment_draft_invoice_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="draft_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="draft_payment_set",
                to="invoices.invoice",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="paid_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="paid_payment_set",
                to="invoices.invoice",
            ),
        ),
    ]
