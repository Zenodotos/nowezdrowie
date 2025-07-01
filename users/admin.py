from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Dodatkowe informacje', {
            'fields': ('phone', 'role', 'created_at', 'updated_at')
        }),
    )
    
    
    readonly_fields = ('created_at', 'updated_at')
    
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    

    list_filter = BaseUserAdmin.list_filter + ('role', 'created_at')
    
  
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
