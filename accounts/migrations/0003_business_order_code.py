import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_business_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="order_code",
            field=models.UUIDField(null=True, editable=False),
        ),
    ]
