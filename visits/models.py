# visits/models.py
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


class StatusType(models.Model):
    """Statusy kart wizyt i dozwolone przejścia"""
    
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
    
    name = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        unique=True,
        verbose_name='Nazwa statusu'
    )
    order_sequence = models.PositiveIntegerField(
        verbose_name='Kolejność',
        help_text='Kolejność wyświetlania statusów'
    )
    allows_transition_to = models.JSONField(
        default=list,
        verbose_name='Dozwolone przejścia statusów',
        help_text='Lista statusów na które można przejść z tego statusu'
    )
    
    class Meta:
        db_table = 'tenant_schema_statustypes'
        verbose_name = 'Typ statusu'
        verbose_name_plural = 'Typy statusów'
        ordering = ['order_sequence']
    
    def __str__(self):
        return self.get_name_display()
    
    def can_transition_to(self, target_status):
        """Sprawdza czy można przejść do docelowego statusu"""
        return target_status in self.allows_transition_to


class VisitCard(models.Model):
    """Rdzeń systemu - karty wizyt pacjentów"""
    
    QUESTIONNAIRE_LOCATION_CHOICES = [
        ('ikp', 'IKP'),
        ('poz', 'POZ'),
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
    
    status = models.ForeignKey(
        StatusType,
        on_delete=models.CASCADE,
        related_name='visit_cards',
        verbose_name='Status'
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
        return f"{self.patient.get_decrypted_full_name()} - {self.visit_type} ({self.status})"
    
    @property
    def is_active(self):
        """Sprawdza czy wizyta jest aktywna (nie anulowana i nie zakończona)"""
        return not self.is_cancelled and self.status.name not in ['zakończone', 'odwołane']
    
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
    
    def can_change_status_to(self, new_status):
        """Sprawdza czy można zmienić status na nowy"""
        if isinstance(new_status, str):
            return self.status.can_transition_to(new_status)
        return self.status.can_transition_to(new_status.name)
    
    def change_status(self, new_status, user=None):
        """Zmienia status wizyty z walidacją"""
        if not self.can_change_status_to(new_status):
            raise ValidationError(
                f"Nie można zmienić statusu z '{self.status}' na '{new_status}'"
            )
        
        if isinstance(new_status, str):
            new_status_obj = StatusType.objects.get(name=new_status)
        else:
            new_status_obj = new_status
        
        self.status = new_status_obj
        
        # Automatyczne wypełnianie dat na podstawie statusu
        if new_status_obj.name == 'przyjęte_do_realizacji' and not self.accepted_for_realization_date:
            self.accepted_for_realization_date = timezone.now().date()
        elif new_status_obj.name == 'wystawiono_skierowanie' and not self.referral_issued_date:
            self.referral_issued_date = timezone.now().date()
        elif new_status_obj.name == 'wizyta_odbyta' and not self.visit_completed_date:
            self.visit_completed_date = timezone.now().date()
        
        self.save()
    
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