from django.db import migrations

DEFAULT_UNITS = [
    ("Kilogram", "kg"),
    ("Gram", "g"),
    ("Litre", "L"),
    ("Millilitre", "ml"),
    ("Piece", "pc"),
    ("Dozen", "dozen"),
    ("Box", "box"),
    ("Packet", "packet"),
    ("Bundle", "bundle"),
]


def seed_units(apps, schema_editor):
    Unit = apps.get_model("inventory", "Unit")
    for name, abbreviation in DEFAULT_UNITS:
        Unit.objects.get_or_create(business=None, abbreviation=abbreviation, defaults={"name": name})


def remove_units(apps, schema_editor):
    Unit = apps.get_model("inventory", "Unit")
    Unit.objects.filter(
        business=None, abbreviation__in=[abbr for _, abbr in DEFAULT_UNITS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_units, remove_units),
    ]
