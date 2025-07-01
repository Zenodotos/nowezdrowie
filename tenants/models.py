from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    created_on = models.DateField(auto_now_add=True)
    auto_create_schema = True

class Domain(DomainMixin):
    pass

class Package(models.Model):
    name = models.CharField(max_length=50)          
    slug = models.SlugField(unique=True)             
    price = models.DecimalField(max_digits=8, decimal_places=2)
    max_users = models.IntegerField(null=True, blank=True)       
    features = models.JSONField(default=dict)        
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

class Subscription(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='subscriptions')
    package = models.ForeignKey(Package, on_delete=models.PROTECT)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tenant', 'package', 'start_date')