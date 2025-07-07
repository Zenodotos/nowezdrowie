
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.db import models
from django import forms
from .models import Patient, ProgramParticipationHistory


class PatientAdminForm(forms.ModelForm):
    """Custom formularz dla admin pacjentów"""
    
    class Meta:
        model = Patient
        fields = [
            'pesel_encrypted',
            'first_name_encrypted', 
            'last_name_encrypted',
            'email',
            'phone'
        ]
        widgets = {
            'pesel_encrypted': forms.TextInput(attrs={
                'placeholder': 'Wprowadź 11-cyfrowy numer PESEL',
                'maxlength': 11,
                'pattern': '[0-9]{11}'
            }),
            'first_name_encrypted': forms.TextInput(attrs={
                'placeholder': 'Wprowadź imię pacjenta'
            }),
            'last_name_encrypted': forms.TextInput(attrs={
                'placeholder': 'Wprowadź nazwisko pacjenta'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'email@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+48123456789'
            })
        }
    
    def clean_pesel_encrypted(self):
        pesel = self.cleaned_data.get('pesel_encrypted')
        if pesel:
            try:
                Patient.validate_pesel(pesel)
            except ValidationError as e:
                raise forms.ValidationError(f"Nieprawidłowy PESEL: {e}")
        return pesel
    
    def clean(self):
        cleaned_data = super().clean()
        pesel = cleaned_data.get('pesel_encrypted')
        
        if pesel:
            try:
                birth_date, gender = Patient.extract_pesel_data(pesel)
                # Dodaj informacje do cleaned_data (ale nie do pól formularza)
                cleaned_data['_extracted_birth_date'] = birth_date
                cleaned_data['_extracted_gender'] = gender
            except ValidationError as e:
                self.add_error('pesel_encrypted', f"Błąd wyciągania danych z PESEL: {e}")
        
        return cleaned_data


class CustomPatientSearchMixin:
    """Mixin dodający custom wyszukiwanie do admin"""
    
    def get_search_results(self, request, queryset, search_term):
        """
        Custom wyszukiwanie które obsługuje zaszyfrowane pola
        """
        if not search_term:
            return queryset, False
        
        # Standardowe wyszukiwanie po niezaszyfrowanych polach
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        # Dodatkowe wyszukiwanie po zaszyfrowanych polach
        search_results = models.Q()
        
        # Wyszukiwanie po PESEL (jeśli search_term wygląda jak PESEL)
        if search_term.isdigit() and len(search_term) >= 3:
            try:
                patients_by_pesel = Patient.objects.search_by_pesel(search_term)
                if patients_by_pesel.exists():
                    search_results |= models.Q(id__in=patients_by_pesel.values_list('id', flat=True))
            except:
                pass
        
        # Wyszukiwanie po imieniu/nazwisku
        if search_term.isalpha():
            try:
                # Spróbuj jako pojedyncze imię
                patients_by_first_name = Patient.objects.search_by_name(first_name=search_term)
                if patients_by_first_name.exists():
                    search_results |= models.Q(id__in=patients_by_first_name.values_list('id', flat=True))
                
                # Spróbuj jako nazwisko
                patients_by_last_name = Patient.objects.search_by_name(last_name=search_term)
                if patients_by_last_name.exists():
                    search_results |= models.Q(id__in=patients_by_last_name.values_list('id', flat=True))
            except:
                pass
        
        # Wyszukiwanie po pełnym imieniu i nazwisku
        if ' ' in search_term:
            try:
                patients_by_full_name = Patient.objects.search_by_full_name(search_term)
                if patients_by_full_name.exists():
                    search_results |= models.Q(id__in=patients_by_full_name.values_list('id', flat=True))
            except:
                pass
        
        # Połącz wyniki
        if search_results:
            queryset = queryset.filter(search_results)
            use_distinct = True
        
        return queryset, use_distinct


class ProgramParticipationHistoryInline(admin.TabularInline):
    """Inline do wyświetlania historii programów w panelu pacjenta"""
    model = ProgramParticipationHistory
    extra = 1
    readonly_fields = ('created_at',)


@admin.register(Patient)
class PatientAdmin(CustomPatientSearchMixin, admin.ModelAdmin):
    form = PatientAdminForm
    
    list_display = [
        'id',
        'get_patient_name',
        'get_masked_pesel', 
        'date_of_birth', 
        'age', 
        'gender',
        'email', 
        'phone', 
        'created_at'
    ]
    
    list_filter = [
        'gender',
        'date_of_birth',
        'created_at',
        'updated_at',
    ]
    
    # Wyszukiwanie - obsługiwane przez CustomPatientSearchMixin
    search_fields = [
        'email',    # Standardowe wyszukiwanie po email
        'phone',    # Standardowe wyszukiwanie po telefonie
        # Zaszyfrowane pola są obsługiwane przez get_search_results
    ]
    
    readonly_fields = [
        'date_of_birth', 
        'gender', 
        'age',
        'created_at', 
        'updated_at',
        'get_pesel_info',
        'pesel_hash',
        'first_name_hash',
        'last_name_hash'
    ]
    
    fieldsets = (
        ('Dane osobowe', {
            'fields': (
                'pesel_encrypted',
                'first_name_encrypted', 
                'last_name_encrypted',
            ),
            'classes': ('wide',),
            'description': 'Dane osobowe są automatycznie szyfrowane po zapisaniu'
        }),
        ('Informacje z PESEL (automatyczne)', {
            'fields': (
                'get_pesel_info',
                'date_of_birth', 
                'gender', 
                'age'
            ),
            'classes': ('collapse',),
            'description': 'Te pola są automatycznie wypełniane na podstawie numeru PESEL'
        }),
        ('Dane kontaktowe', {
            'fields': ('email', 'phone'),
        }),
        ('Dane techniczne (ukryte)', {
            'fields': (
                'pesel_hash',
                'first_name_hash', 
                'last_name_hash'
            ),
            'classes': ('collapse',),
            'description': 'Te pola zawierają hasze używane tylko do wyszukiwania'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [ProgramParticipationHistoryInline]
    
    def get_patient_name(self, obj):
        """Wyświetla odszyfrowane imię i nazwisko"""
        try:
            return obj.get_decrypted_full_name()
        except:
            return "Błąd odszyfrowania"
    get_patient_name.short_description = 'Imię i nazwisko'
    
    def get_masked_pesel(self, obj):
        """Wyświetla zamaskowany PESEL dla bezpieczeństwa"""
        if obj.pesel_encrypted:
            return obj.get_masked_pesel()
        return "Brak PESEL"
    get_masked_pesel.short_description = 'PESEL (zamaskowany)'
    
    def age(self, obj):
        age = obj.age
        return age if age is not None else "Brak daty urodzenia"
    age.short_description = 'Wiek'
    
    def get_pesel_info(self, obj):
        """Wyświetla informacje wyciągnięte z PESEL"""
        if obj.pesel_encrypted:
            try:
                birth_date, gender = Patient.extract_pesel_data(obj.pesel_encrypted)
                return format_html(
                    "<div style='background: #f8f9fa; padding: 10px; border-radius: 5px;'>"
                    "<strong>📅 Data urodzenia:</strong> {}<br>"
                    "<strong>👤 Płeć:</strong> {}<br>"
                    "<strong>🔒 PESEL:</strong> {}<br>"
                    "<strong>🎂 Wiek:</strong> {} lat"
                    "</div>",
                    birth_date.strftime("%d.%m.%Y"),
                    "Kobieta" if gender == 'K' else "Mężczyzna",
                    obj.get_masked_pesel(),
                    obj.age or "Nie obliczono"
                )
            except ValidationError as e:
                return format_html(
                    "<div style='background: #f8d7da; padding: 10px; border-radius: 5px; color: #721c24;'>"
                    "<strong>⚠️ Błąd PESEL:</strong> {}"
                    "</div>",
                    str(e)
                )
        return format_html(
            "<div style='background: #fff3cd; padding: 10px; border-radius: 5px; color: #856404;'>"
            "ℹ️ Brak numeru PESEL"
            "</div>"
        )
    get_pesel_info.short_description = 'Informacje z PESEL'
    
    def save_model(self, request, obj, form, change):
        """Dodatkowa walidacja przed zapisem"""
        try:
            # Walidacja PESEL jeśli został podany
            if obj.pesel_encrypted:
                try:
                    Patient.validate_pesel(obj.pesel_encrypted)
                except ValidationError as pesel_error:
                    form.add_error('pesel_encrypted', f"Nieprawidłowy PESEL: {pesel_error}")
                    return
            
            super().save_model(request, obj, form, change)
            
            # Wyświetl komunikat o sukcesie z dodatkowymi informacjami
            if obj.pesel_encrypted:
                try:
                    birth_date, gender = Patient.extract_pesel_data(obj.pesel_encrypted)
                    self.message_user(
                        request,
                        f"Pacjent zapisany pomyślnie. "
                        f"Automatycznie wypełniono: data urodzenia {birth_date.strftime('%d.%m.%Y')}, "
                        f"płeć: {'Kobieta' if gender == 'K' else 'Mężczyzna'}"
                    )
                except:
                    pass
            
        except ValidationError as e:
            # Obsłuż błędy walidacji
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    if field in form.fields:
                        form.add_error(field, errors)
                    else:
                        # Jeśli pole nie jest w formularzu, dodaj jako ogólny błąd
                        form.add_error(None, f"{field}: {'; '.join(str(err) for err in errors)}")
            else:
                form.add_error(None, str(e))
        except Exception as e:
            form.add_error(None, f"Błąd zapisu: {str(e)}")
    
    def get_queryset(self, request):
        """Optymalizacja zapytań"""
        return super().get_queryset(request).select_related()
    
    # Dodatkowe akcje admin
    actions = ['test_decryption', 'regenerate_hashes']
    
    def test_decryption(self, request, queryset):
        """Akcja testująca odszyfrowanie danych"""
        success_count = 0
        error_count = 0
        
        for patient in queryset:
            try:
                name = patient.get_decrypted_full_name()
                pesel = patient.get_decrypted_pesel()
                success_count += 1
            except Exception:
                error_count += 1
        
        self.message_user(
            request,
            f"Odszyfrowanie: {success_count} udanych, {error_count} błędów"
        )
    test_decryption.short_description = "Testuj odszyfrowanie wybranych pacjentów"
    
    def regenerate_hashes(self, request, queryset):
        """Akcja regenerująca hasze wyszukiwania"""
        count = 0
        for patient in queryset:
            patient.save()  # save() automatycznie regeneruje hasze
            count += 1
        
        self.message_user(
            request,
            f"Zregenerowano hasze dla {count} pacjentów"
        )
    regenerate_hashes.short_description = "Regeneruj hasze wyszukiwania"


@admin.register(ProgramParticipationHistory)
class ProgramParticipationHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'patient',
        'get_patient_name',
        'program_type',
        'participation_year',
        'is_current_year',
        'years_since_participation',
        'created_at'
    ]
    
    list_filter = [
        'program_type',
        'participation_year',
        'created_at'
    ]
    
    # Wyszukiwanie - możemy wyszukiwać po ID pacjenta lub danych kontaktowych
    search_fields = [
        'patient__id',
        'patient__email',
        'patient__phone',
    ]
    
    readonly_fields = ['created_at']
    
    autocomplete_fields = ['patient']  # Autocomplete dla wyboru pacjenta
    
    fieldsets = (
        ('Informacje podstawowe', {
            'fields': ('patient', 'program_type', 'participation_year'),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    def get_patient_name(self, obj):
        """Wyświetla imię i nazwisko pacjenta"""
        try:
            return obj.patient.get_decrypted_full_name()
        except:
            return "Błąd odszyfrowania"
    get_patient_name.short_description = 'Imię i nazwisko pacjenta'
    
    def is_current_year(self, obj):
        return obj.is_current_year
    is_current_year.boolean = True
    is_current_year.short_description = 'Bieżący rok'
    
    def years_since_participation(self, obj):
        return f"{obj.years_since_participation} lat"
    years_since_participation.short_description = 'Lat od uczestnictwa'
    
    def get_queryset(self, request):
        """Optymalizacja zapytań"""
        return super().get_queryset(request).select_related('patient')


# Dodatkowe customizacje admin interface
admin.site.site_header = "System Zarządzania Pacjentami"
admin.site.site_title = "Panel Administracyjny"
admin.site.index_title = "Zarządzanie danymi medycznymi"