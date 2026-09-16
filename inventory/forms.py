from django import forms
from django.db.models import Q

from .models import Product, Unit


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "unit", "stock_qty", "cost_price", "selling_price", "is_active"]

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.business = business
        self.fields["unit"].queryset = (
            Unit.objects.filter(Q(business=business) | Q(business__isnull=True))
            if business
            else Unit.objects.none()
        )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Product.objects.for_business(self.business).filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("You already have a product with this name.")
        return name


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["name", "abbreviation"]
