# Generated by Django 5.1.3 on 2024-12-19 10:26

from django.db import migrations


def fill_in_invoice(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    for payment in Payment.objects.filter(
        invoice="", paid_invoice__isnull=False
    ).select_related("paid_invoice"):
        payment.invoice = payment.paid_invoice.number
        payment.save(update_fields=["invoice"])


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0042_alter_customer_name"),
    ]

    operations = [
        migrations.RunPython(fill_in_invoice, migrations.RunPython.noop, elidable=True),
    ]
