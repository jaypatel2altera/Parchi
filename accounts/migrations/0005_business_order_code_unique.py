import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_backfill_order_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="business",
            name="order_code",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
