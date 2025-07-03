from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import date
from encrypted_model_fields.fields import EncryptedCharField
import hashlib
from django.conf import settings


class PatientManager(models.Manager):
    """Custom manager dla wyszukiwania pacjentów po zaszyfrowanych danych"""
    
    def search_by_pesel(self, pesel):
        """Wyszukiwanie pacjenta po numerze PESEL"""
        # Tworzymy hash PESEL dla porównania
        pesel_hash = self._create_search_hash(pesel)
        return self.filter(pesel_hash=pesel_hash)
    
    def search_by_name(self, first_name=None, last_name=None):
        """Wyszukiwanie pacjenta po imieniu i/lub nazwisku"""
        queryset = self.get_queryset()
        
        if first_name:
            first_name_hash = self._create_search_hash(first_name.lower())
            queryset = queryset.filter(first_name_hash=first_name_hash)
            
        if last_name:
            last_name_hash = self._create_search_hash(last_name.lower())
            queryset = queryset.filter(last_name_hash=last_name_hash)
            
        return queryset
    
    def search_by_full_name(self, full_name):
        """Wyszukiwanie po pełnym imieniu i nazwisku"""
        parts = full_name.strip().split()
        if len(parts) >= 2:
            return self.search_by_name(first_name=parts[0], last_name=' '.join(parts[1:]))
        elif len(parts) == 1:
            # Szukaj w imieniu lub nazwisku
            name_hash = self._create_search_hash(parts[0].lower())
            return self.filter(
                models.Q(first_name_hash=name_hash) | models.Q(last_name_hash=name_hash)
            )
        return self.none()
    
    def _create_search_hash(self, value):
        """Tworzy hash do wyszukiwania"""
        if not value:
            return None
        
        # Używamy salt z settings + wartość
        salt = getattr(settings, 'PATIENT_SEARCH_SALT', 'default_salt')
        hash_input = f"{salt}{value.lower().strip()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()


class Patient(models.Model):
    """Model pacjenta z zaszyfrowanymi danymi osobowymi"""
    
    GENDER_CHOICES = [
        ('M', 'Mężczyzna'),
        ('K', 'Kobieta'),
    ]
    
    # Zaszyfrowane pola (nullable dla migracji istniejących danych)
    pesel_encrypted = EncryptedCharField(
        max_length=11,
        null=True,
        blank=True,
        verbose_name='Zaszyfrowany PESEL',
        help_text='PESEL pacjenta w formie zaszyfrowanej'
    )
    
    first_name_encrypted = EncryptedCharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='Zaszyfrowane imię'
    )
    
    last_name_encrypted = EncryptedCharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='Zaszyfrowane nazwisko'
    )
    
    # Hasze do wyszukiwania (nie są szyfrowane, tylko zahashowane)
    pesel_hash = models.CharField(
        max_length=64,
        db_index=True,
        null=True,
        blank=True,
        verbose_name='Hash PESEL do wyszukiwania',
        help_text='Hash numeru PESEL używany tylko do wyszukiwania'
    )
    
    first_name_hash = models.CharField(
        max_length=64,
        db_index=True,
        null=True,
        blank=True,
        verbose_name='Hash imienia do wyszukiwania',
        help_text='Hash imienia używany tylko do wyszukiwania'
    )
    
    last_name_hash = models.CharField(
        max_length=64,
        db_index=True,
        null=True,
        blank=True,
        verbose_name='Hash nazwiska do wyszukiwania',
        help_text='Hash nazwiska używany tylko do wyszukiwania'
    )
    
    # Niezaszyfrowane pola kontaktowe
    email = models.EmailField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Adres email'
    )
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Numer telefonu musi być w formacie: '+999999999'. Dozwolone do 15 cyfr."
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Numer telefonu'
    )
    
    # Automatycznie wyciągane z PESEL
    date_of_birth = models.DateField(
        verbose_name='Data urodzenia',
        help_text='Automatycznie wyciągana z PESEL'
    )
    
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        verbose_name='Płeć',
        help_text='Automatycznie wyciągana z PESEL'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data utworzenia'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data ostatniej aktualizacji'
    )
    
    # Custom manager
    objects = PatientManager()
    
    class Meta:
        db_table = 'tenant_schema_patients'
        verbose_name = 'Pacjent'
        verbose_name_plural = 'Pacjenci'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pesel_hash']),
            models.Index(fields=['first_name_hash']),
            models.Index(fields=['last_name_hash']),
            models.Index(fields=['date_of_birth']),
            models.Index(fields=['gender']),
        ]
    
    def __str__(self):
        try:
            return f"{self.get_decrypted_full_name()} (ur. {self.date_of_birth})"
        except:
            return f"Pacjent #{self.id}"
    
    @property
    def age(self):
        """Oblicza wiek pacjenta"""
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


    @property
    def can_start_40plus_visit(self):
        """Sprawdza czy pacjent może przystąpić do wizyty 40+ (raz na rok)"""
        from datetime import datetime, timedelta
        from visits.models import VisitCard
        

        has_open_40plus = self.visit_cards.filter(
            visit_type__name='40+',
            is_cancelled=False
        ).exists()
        
        if has_open_40plus or self.age < 40:
            return False
        
        one_year_ago = datetime.now().date() - timedelta(days=365)
        recent_40plus = self.visit_cards.filter(
            visit_type__name='40+',
            visit_status='zakończone',
            visit_completed_date__gte=one_year_ago
        ).exists()
        
        return not recent_40plus

    @property
    def current_40plus_visit(self):
        return self.visit_cards.filter(
            visit_type__name='40+',
            is_cancelled=False,
            visit_status__in=['oczekiwanie', 'przyjęte_do_realizacji', 'badania_w_toku']
        ).first()
    
    def get_decrypted_pesel(self):
        """Zwraca odszyfrowany PESEL"""
        return self.pesel_encrypted or "Brak PESEL"
    
    def get_decrypted_first_name(self):
        """Zwraca odszyfrowane imię"""
        return self.first_name_encrypted or "Brak imienia"
    
    def get_decrypted_last_name(self):
        """Zwraca odszyfrowane nazwisko"""
        return self.last_name_encrypted or "Brak nazwiska"
    
    def get_decrypted_full_name(self):
        """Zwraca odszyfrowane pełne imię i nazwisko"""
        first_name = self.first_name_encrypted or ""
        last_name = self.last_name_encrypted or ""
        full_name = f"{first_name} {last_name}".strip()
        return full_name if full_name else f"Pacjent #{self.id}"
    
    def get_masked_pesel(self):
        """Zwraca zamaskowany PESEL dla bezpieczeństwa"""
        try:
            pesel = str(self.pesel_encrypted)
            if len(pesel) == 11:
                return f"{pesel[:2]}***{pesel[5:7]}***{pesel[9:]}"
            return "***masked***"
        except:
            return "Błąd"
    
    def save(self, *args, **kwargs):
        """
        Automatyczne wypełnianie danych na podstawie PESEL i tworzenie hashów
        """
        if self.pesel_encrypted:
            # Walidacja i wyciąganie danych z PESEL
            try:
                birth_date, gender = self.extract_pesel_data(self.pesel_encrypted)
                self.date_of_birth = birth_date
                self.gender = gender
            except ValidationError as e:
                raise ValidationError(f"Błąd PESEL: {e}")
            
            # Tworzenie hashu PESEL do wyszukiwania
            self.pesel_hash = self._create_search_hash(self.pesel_encrypted)
        
        # Tworzenie hashów imienia i nazwiska do wyszukiwania
        if self.first_name_encrypted:
            self.first_name_hash = self._create_search_hash(self.first_name_encrypted.lower())
        
        if self.last_name_encrypted:
            self.last_name_hash = self._create_search_hash(self.last_name_encrypted.lower())
        
        super().save(*args, **kwargs)
    
    def _create_search_hash(self, value):
        """Tworzy hash do wyszukiwania"""
        if not value:
            return None
        
        salt = getattr(settings, 'PATIENT_SEARCH_SALT', 'default_salt')
        hash_input = f"{salt}{value.lower().strip()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    @staticmethod
    def validate_pesel(pesel):
        """Walidacja numeru PESEL"""
        if not pesel or len(pesel) != 11:
            raise ValidationError("PESEL musi mieć dokładnie 11 cyfr")
        
        if not pesel.isdigit():
            raise ValidationError("PESEL może zawierać tylko cyfry")
        
        # Walidacja sumy kontrolnej
        weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
        checksum = sum(int(pesel[i]) * weights[i] for i in range(10)) % 10
        control_digit = (10 - checksum) % 10
        
        if int(pesel[10]) != control_digit:
            raise ValidationError("Nieprawidłowa suma kontrolna PESEL")
        
        return True
    
    @staticmethod
    def extract_pesel_data(pesel):
        """
        Wyciąga datę urodzenia i płeć z numeru PESEL
        """
        Patient.validate_pesel(pesel)
        
        # Wyciągnij komponenty
        year = int(pesel[:2])
        month = int(pesel[2:4])
        day = int(pesel[4:6])
        gender_digit = int(pesel[9])  # 10. cyfra (indeks 9)
        
        # Określ pełny rok na podstawie miesiąca
        if month > 80:  # 1800-1899
            full_year = 1800 + year
            actual_month = month - 80
        elif month > 60:  # 2200-2299
            full_year = 2200 + year
            actual_month = month - 60
        elif month > 40:  # 2100-2199
            full_year = 2100 + year
            actual_month = month - 40
        elif month > 20:  # 2000-2099
            full_year = 2000 + year
            actual_month = month - 20
        else:  # 1900-1999
            full_year = 1900 + year
            actual_month = month
        
        # Walidacja daty
        try:
            birth_date = date(full_year, actual_month, day)
        except ValueError:
            raise ValidationError(f"Nieprawidłowa data urodzenia w PESEL: {day}.{actual_month}.{full_year}")
        
        # Określ płeć (przedostatnia cyfra)
        # Parzysta = kobieta, nieparzysta = mężczyzna
        gender = 'K' if gender_digit % 2 == 0 else 'M'
        
        return birth_date, gender
    
    def clean(self):
        """Dodatkowa walidacja modelu"""
        if self.pesel_encrypted:
            try:
                self.extract_pesel_data(self.pesel_encrypted)
            except ValidationError as e:
                raise ValidationError({'pesel_encrypted': str(e)})
    
    # Metody wyszukiwania jako metody instancji
    @classmethod
    def find_by_pesel(cls, pesel):
        """Znajdź pacjenta po numerze PESEL"""
        return cls.objects.search_by_pesel(pesel).first()
    
    @classmethod
    def find_by_name(cls, first_name=None, last_name=None):
        """Znajdź pacjentów po imieniu i/lub nazwisku"""
        return cls.objects.search_by_name(first_name, last_name)
    
    @classmethod
    def find_by_full_name(cls, full_name):
        """Znajdź pacjentów po pełnym imieniu i nazwisku"""
        return cls.objects.search_by_full_name(full_name)


class ProgramParticipationHistory(models.Model):
    """Historia uczestnictwa pacjentów w programach profilaktycznych"""
    
    PROGRAM_TYPES = [
        ('40+', 'Program 40+'),
        ('inne', 'Inne programy'),
    ]
    
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='program_history',
        verbose_name='Pacjent'
    )
    
    participation_year = models.PositiveIntegerField(
        verbose_name='Rok uczestnictwa',
        help_text='Rok, w którym pacjent uczestniczył w programie'
    )
    
    program_type = models.CharField(
        max_length=10,
        choices=PROGRAM_TYPES,
        verbose_name='Typ programu'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data utworzenia wpisu'
    )
    
    class Meta:
        db_table = 'tenant_schema_programparticipationhistory'
        verbose_name = 'Historia uczestnictwa w programie'
        verbose_name_plural = 'Historia uczestnictwa w programach'
        unique_together = ['patient', 'participation_year', 'program_type']
        ordering = ['-participation_year', 'patient']
    
    def __str__(self):
        return f"{self.patient} - {self.get_program_type_display()} ({self.participation_year})"
    
    @property
    def is_current_year(self):
        """Sprawdza czy uczestnictwo dotyczy bieżącego roku"""
        return self.participation_year == timezone.now().year
    
    @property
    def years_since_participation(self):
        """Oblicza ile lat minęło od uczestnictwa"""
        return timezone.now().year - self.participation_year