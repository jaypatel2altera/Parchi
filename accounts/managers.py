from django.db import models


class BusinessScopedQuerySet(models.QuerySet):
    def for_business(self, business):
        return self.filter(business=business)


class BusinessScopedManager(models.Manager):
    """Manager for tenant-scoped models. Convention: views must fetch rows via
    `Model.objects.for_business(request.business)`, never a bare `.filter()`,
    so a business's data can never leak into another business's queryset."""

    def get_queryset(self):
        return BusinessScopedQuerySet(self.model, using=self._db)

    def for_business(self, business):
        return self.get_queryset().for_business(business)
