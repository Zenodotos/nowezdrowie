from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from patients.models import Patient


class VisitType(models.Model):
    """Typy wizyt dostępne u tenanta"""
    
    name = models.CharField(
        max_length=255,
        verbose_name='Nazwa typu wizyty'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Opis'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktywny'
    )
    
    class Meta:
        db_table = 'tenant_schema_visittypes'
        verbose_name = 'Typ wizyty'
        verbose_name_plural = 'Typy wizyt'
        ordering = ['name']
    
    def __str__(self):
        return self.name





class VisitCard(models.Model):
    """Rdzeń systemu - karty wizyt pacjentów"""
    
    QUESTIONNAIRE_LOCATION_CHOICES = [
        ('ikp', 'IKP'),
        ('poz', 'POZ'),
    ]

    STATUS_CHOICES = [
    ('oczekiwanie', 'Oczekiwanie'),
    ('przyjęte_do_realizacji', 'Przyjęte do realizacji'),
    ('wystawiono_skierowanie', 'Wystawiono skierowanie'),
    ('badania_w_toku', 'Badania w toku'),
    ('wizyta_odbyta', 'Wizyta odbyta'),
    ('interwencja', 'Interwencja'),
    ('zakończone', 'Zakończone'),
    ('odwołane', 'Odwołane'),
    ]
    
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='visit_cards',
        verbose_name='Pacjent'
    )
    
    visit_type = models.ForeignKey(
        VisitType,
        on_delete=models.CASCADE,
        related_name='visit_cards',
        verbose_name='Typ wizyty'
    )
    
    
    questionnaire_completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_questionnaires',
        verbose_name='Ankietę wypełnił'
    )
    
    questionnaire_location = models.CharField(
        max_length=10,
        choices=QUESTIONNAIRE_LOCATION_CHOICES,
        null=True,
        blank=True,
        verbose_name='Miejsce wypełnienia ankiety'
    )

    visit_status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='oczekiwanie',
        verbose_name='Status karty'

    )
    
    questionnaire_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data wypełnienia ankiety'
    )
    
    accepted_for_realization_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data przyjęcia do realizacji'
    )
    
    referral_issued_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data wystawienia skierowania'
    )
    
    referral_expires_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data ważności skierowania'
    )
    
    visit_completed_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data odbycia wizyty'
    )
    
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coordinated_visits',
        verbose_name='Koordynator'
    )
    
    current_responsible_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_visits',
        verbose_name='Aktualnie odpowiedzialny'
    )
    
    comments = models.TextField(
        blank=True,
        null=True,
        verbose_name='Komentarze'
    )
    
    is_cancelled = models.BooleanField(
        default=False,
        verbose_name='Anulowana'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data utworzenia'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data ostatniej aktualizacji'
    )
    
    class Meta:
        db_table = 'tenant_schema_visitcards'
        verbose_name = 'Karta wizyty'
        verbose_name_plural = 'Karty wizyt'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.patient.get_decrypted_full_name()} - {self.visit_type} ({self.get_visit_status_display()})"
    
    @property
    def is_active(self):
        return not self.is_cancelled and self.visit_status not in ['zakończone', 'odwołane']
    
    @property
    def days_since_created(self):
        """Ile dni minęło od utworzenia karty"""
        return (timezone.now().date() - self.created_at.date()).days
    
    @property
    def is_referral_expired(self):
        """Sprawdza czy skierowanie wygasło"""
        if not self.referral_expires_date:
            return False
        return self.referral_expires_date < timezone.now().date()
    
    
    def clean(self):
        """Walidacja modelu"""
        super().clean()
        
        # Sprawdź czy data ważności skierowania nie jest wcześniejsza niż data wystawienia
        if (self.referral_issued_date and self.referral_expires_date and 
            self.referral_expires_date < self.referral_issued_date):
            raise ValidationError(
                'Data ważności skierowania nie może być wcześniejsza niż data wystawienia'
            )
        
        # Sprawdź czy data odbycia wizyty nie jest wcześniejsza niż data utworzenia
        if (self.visit_completed_date and self.created_at and 
            self.visit_completed_date < self.created_at.date()):
            raise ValidationError(
                'Data odbycia wizyty nie może być wcześniejsza niż data utworzenia karty'
            )