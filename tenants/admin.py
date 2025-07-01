from django.contrib import admin


from tenants.models import Tenant, Domain, Subscription, Package

admin.site.register(Tenant)
admin.site.register(Domain)
admin.site.register(Subscription)
admin.site.register(Package)
