from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.utils.text import slugify

from .models import Business, Membership

User = get_user_model()


class SignupForm(UserCreationForm):
    business_name = forms.CharField(max_length=150, label="Business name")
    email = forms.EmailField(label="Business email")
    phone = forms.CharField(max_length=15, label="Business mobile number")

    field_order = ["business_name", "email", "phone", "username", "password1", "password2"]

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=True)
        base_slug = slugify(self.cleaned_data["business_name"]) or "business"
        slug = base_slug
        counter = 1
        while Business.objects.filter(slug=slug).exists():
            counter += 1
            slug = f"{base_slug}-{counter}"
        business = Business.objects.create(
            name=self.cleaned_data["business_name"],
            slug=slug,
            owner=user,
            email=self.cleaned_data["email"],
            phone=self.cleaned_data["phone"],
        )
        Membership.objects.create(user=user, business=business, role=Membership.ADMIN)
        return user


class StaffCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)


class BusinessSettingsForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["name", "email", "phone", "address"]


class StaffProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
