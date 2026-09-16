from django import forms


class BillCustomerForm(forms.Form):
    customer_name = forms.CharField(max_length=100, required=False, label="Customer name (optional)")
    customer_phone = forms.CharField(
        max_length=15,
        required=False,
        label="Customer WhatsApp number (optional)",
        help_text="With country code, e.g. 91XXXXXXXXXX",
    )
