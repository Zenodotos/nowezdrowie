# visits/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from .models import VisitType, StatusType, VisitCard


@admin.register(VisitType)
class VisitTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'visit_count']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    
    def visit_count(self, obj):
        return obj.visit_cards.count()
    visit_count.short_description = 'Liczba wizyt'


@admin.register(StatusType)
class StatusTypeAdmin(admin.ModelAdmin):
    list_display = ['get_name_display']

    
    def transition_count(self, obj):
        return len(obj.allows_transition_to)
    transition_count.short_description = 'Dozwolone przejścia'


@admin.register(VisitCard)
class VisitCardAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'get_patient_name',
        'visit_type',
        'status_badge',
        'questionnaire_date',
        'visit_completed_date',
        'is_active',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'visit_type',
        'questionnaire_location',
        'is_cancelled',
        'created_at'
    ]
    
    search_fields = [
        'patient__pesel_search',
        'patient__first_name_search',
        'patient__last_name_search',
        'patient__email'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'is_active',
        'days_since_created',
        'is_referral_expired'
    ]
    
    fieldsets = (
        ('Podstawowe informacje', {
            'fields': (
                'patient',
                'visit_type',
                'status',
                'current_responsible_person',
                'coordinator'
            )
        }),
        ('Ankieta', {
            'fields': (
                'questionnaire_completed_by',
                'questionnaire_location',
                'questionnaire_date'
            ),
            'classes': ('collapse',)
        }),
        ('Daty realizacji', {
            'fields': (
                'accepted_for_realization_date',
                'referral_issued_date',
                'referral_expires_date',
                'visit_completed_date'
            ),
            'classes': ('collapse',)
        }),
        ('Dodatkowe', {
            'fields': (
                'comments',
                'is_cancelled'
            ),
            'classes': ('collapse',)
        }),
        ('Informacje systemowe', {
            'fields': (
                'is_active',
                'days_since_created',
                'is_referral_expired',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_patient_name(self, obj):
        return obj.patient.get_decrypted_full_name()
    get_patient_name.short_description = 'Pacjent'
    
    def status_badge(self, obj):
        colors = {
            'oczekiwanie': 'warning',
            'przyjęte_do_realizacji': 'info', 
            'wystawiono_skierowanie': 'primary',
            'badania_w_toku': 'secondary',
            'wizyta_odbyta': 'success',
            'interwencja': 'dark',
            'zakończone': 'success',
            'odwołane': 'danger'
        }
        color = colors.get(obj.status.name, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    
    actions = ['change_status_action']
    
    def change_status_action(self, request, queryset):
        # Prosty przykład - w rzeczywistości byłaby bardziej zaawansowana forma
        count = queryset.count()
        self.message_user(request, f'Wybrano {count} wizyt do zmiany statusu')
    change_status_action.short_description = 'Zmień status wybranych wizyt'