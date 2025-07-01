# examinations/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import ExaminationType, Examination, Measurement


@admin.register(ExaminationType)
class ExaminationTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'requires_referral', 'is_active', 'examination_count']
    list_filter = ['requires_referral', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['requires_referral', 'is_active']
    
    def examination_count(self, obj):
        return obj.examinations.count()
    examination_count.short_description = 'Liczba badań'


@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'get_patient_name',
        'examination_type',
        'status_badge',
        'scheduled_date',
        'completed_date',
        'is_overdue',
        'performed_by'
    ]
    
    list_filter = [
        'status',
        'examination_type',
        'scheduled_date',
        'completed_date'
    ]
    
    search_fields = [
        'visit_card__patient__pesel_search',
        'visit_card__patient__first_name_search',
        'visit_card__patient__last_name_search',
        'examination_type__name'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'is_completed',
        'is_overdue',
        'days_until_scheduled'
    ]
    
    fieldsets = (
        ('Podstawowe informacje', {
            'fields': (
                'visit_card',
                'examination_type',
                'status'
            )
        }),
        ('Daty', {
            'fields': (
                'scheduled_date',
                'completed_date',
                'days_until_scheduled'
            )
        }),
        ('Personel', {
            'fields': (
                'performed_by',
                'entered_by'
            )
        }),
        ('Wyniki i komentarze', {
            'fields': (
                'results',
                'comments'
            ),
            'classes': ('collapse',)
        }),
        ('Informacje systemowe', {
            'fields': (
                'is_completed',
                'is_overdue',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_patient_name(self, obj):
        return obj.visit_card.patient.get_decrypted_full_name()
    get_patient_name.short_description = 'Pacjent'
    
    def status_badge(self, obj):
        colors = {
            'scheduled': 'primary',
            'in_progress': 'warning',
            'completed': 'success',
            'cancelled': 'danger'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True
    is_overdue.short_description = 'Przeterminowane'
    
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def mark_as_completed(self, request, queryset):
        count = 0
        for examination in queryset.filter(status__in=['scheduled', 'in_progress']):
            examination.complete_examination()
            count += 1
        
        self.message_user(request, f'Oznaczono {count} badań jako zakończone')
    mark_as_completed.short_description = 'Oznacz jako zakończone'
    
    def mark_as_cancelled(self, request, queryset):
        count = queryset.update(status='cancelled')
        self.message_user(request, f'Anulowano {count} badań')
    mark_as_cancelled.short_description = 'Anuluj badania'


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'get_patient_name',
        'measurement_date',
        'blood_pressure_display',
        'pulse',
        'bmi',
        'blood_pressure_category',
        'measured_by'
    ]
    
    list_filter = [
        'measurement_date',
        'blood_pressure_systolic',  # Zmienione z blood_pressure_category
        'measured_by'
    ]
    
    search_fields = [
        'visit_card__patient__pesel_search',
        'visit_card__patient__first_name_search',
        'visit_card__patient__last_name_search'
    ]
    
    readonly_fields = [
        'created_at',
        'blood_pressure_display',
        'blood_pressure_category',
        'bmi_category',
        'waist_hip_ratio'
    ]
    
    fieldsets = (
        ('Podstawowe informacje', {
            'fields': (
                'visit_card',
                'measurement_date'
            )
        }),
        ('Ciśnienie i tętno', {
            'fields': (
                'blood_pressure_systolic',
                'blood_pressure_diastolic',
                'blood_pressure_display',
                'blood_pressure_category',
                'pulse'
            )
        }),
        ('Pomiary antropometryczne', {
            'fields': (
                'waist_circumference',
                'hip_circumference',
                'waist_hip_ratio',
                'bmi',
                'bmi_category'
            )
        }),
        ('Personel i komentarze', {
            'fields': (
                'measured_by',
                'entered_by',
                'comments'
            )
        }),
        ('Informacje systemowe', {
            'fields': (
                'created_at',
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_patient_name(self, obj):
        return obj.visit_card.patient.get_decrypted_full_name()
    get_patient_name.short_description = 'Pacjent'
    
    def blood_pressure_display(self, obj):
        if obj.blood_pressure_display:
            category = obj.blood_pressure_category
            colors = {
                'Optymalne': 'success',
                'Prawidłowe': 'success', 
                'Wysokie prawidłowe': 'warning',
                'Nadciśnienie 1 stopnia': 'danger',
                'Nadciśnienie 2 stopnia': 'danger',
                'Nadciśnienie 3 stopnia': 'danger'
            }
            color = colors.get(category, 'secondary')
            return format_html(
                '<span class="badge bg-{}" title="{}">{} mmHg</span>',
                color,
                category,
                obj.blood_pressure_display
            )
        return '-'
    blood_pressure_display.short_description = 'Ciśnienie'
    
    def blood_pressure_category(self, obj):
        return obj.blood_pressure_category or '-'
    blood_pressure_category.short_description = 'Kategoria ciśnienia'