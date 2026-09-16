import uuid

from django.db import migrations


def backfill_order_codes(apps, schema_editor):
    Business = apps.get_model("accounts", "Business")
    for business in Business.objects.filter(order_code__isnull=True):
        business.order_code = uuid.uuid4()
        business.save(update_fields=["order_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_business_order_code"),
    ]

    operations = [
        migrations.RunPython(backfill_order_codes, migrations.RunPython.noop),
    ]
