# examinations/models.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from visits.models import VisitCard


class ExaminationType(models.Model):
    """Typy badań laboratoryjnych"""
    
    name = models.CharField(
        max_length=255,
        verbose_name='Nazwa badania'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Opis'
    )
    requires_referral = models.BooleanField(
        default=False,
        verbose_name='Wymaga skierowania'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktywny'
    )
    
    class Meta:
        db_table = 'tenant_schema_examinationtypes'
        verbose_name = 'Typ badania'
        verbose_name_plural = 'Typy badań'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Examination(models.Model):
    """Badania laboratoryjne i diagnostyczne"""
    
    STATUS_CHOICES = [
        ('scheduled', 'Zaplanowane'),
        ('in_progress', 'W trakcie'),
        ('completed', 'Zakończone'),
        ('cancelled', 'Anulowane'),
    ]
    
    visit_card = models.ForeignKey(
        VisitCard,
        on_delete=models.CASCADE,
        related_name='examinations',
        verbose_name='Karta wizyty'
    )
    
    examination_type = models.ForeignKey(
        ExaminationType,
        on_delete=models.CASCADE,
        related_name='examinations',
        verbose_name='Typ badania'
    )
    
    scheduled_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data zaplanowana'
    )
    
    completed_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data wykonania'
    )
    
    results = models.JSONField(
        default=dict,
        verbose_name='Wyniki badań',
        help_text='JSONField z wynikami badań'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        verbose_name='Status'
    )
    
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_examinations',
        verbose_name='Wykonał'
    )
    
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entered_examinations',
        verbose_name='Wprowadził'
    )
    
    comments = models.TextField(
        blank=True,
        null=True,
        verbose_name='Komentarze'
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
        db_table = 'tenant_schema_examinations'
        verbose_name = 'Badanie'
        verbose_name_plural = 'Badania'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.examination_type} - {self.visit_card.patient.get_decrypted_full_name()}"
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_overdue(self):
        """Sprawdza czy badanie jest przeterminowane"""
        if not self.scheduled_date or self.status in ['completed', 'cancelled']:
            return False
        return self.scheduled_date < timezone.now().date()
    
    @property
    def days_until_scheduled(self):
        """Ile dni do zaplanowanego badania"""
        if not self.scheduled_date:
            return None
        return (self.scheduled_date - timezone.now().date()).days
    
    def complete_examination(self, results_data=None, performed_by=None):
        """Oznacza badanie jako zakończone"""
        self.status = 'completed'
        self.completed_date = timezone.now().date()
        
        if results_data:
            self.results = results_data
        
        if performed_by:
            self.performed_by = performed_by
        
        self.save()
    
    def clean(self):
        """Walidacja modelu"""
        super().clean()
        
        # Sprawdź czy data wykonania nie jest wcześniejsza niż zaplanowana
        if (self.scheduled_date and self.completed_date and 
            self.completed_date < self.scheduled_date):
            raise ValidationError(
                'Data wykonania nie może być wcześniejsza niż data zaplanowana'
            )
        
        # Jeśli status to 'completed', musi być data wykonania
        if self.status == 'completed' and not self.completed_date:
            self.completed_date = timezone.now().date()


class Measurement(models.Model):
    """Pomiary fizyczne pacjentów"""
    
    visit_card = models.ForeignKey(
        VisitCard,
        on_delete=models.CASCADE,
        related_name='measurements',
        verbose_name='Karta wizyty'
    )
    
    measurement_date = models.DateField(
        verbose_name='Data pomiaru'
    )
    
    # Ciśnienie krwi
    blood_pressure_systolic = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(50),
            MaxValueValidator(300)
        ],
        verbose_name='Ciśnienie skurczowe',
        help_text='mmHg (50-300)'
    )
    
    blood_pressure_diastolic = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(30),
            MaxValueValidator(200)
        ],
        verbose_name='Ciśnienie rozkurczowe',
        help_text='mmHg (30-200)'
    )
    
    # Tętno
    pulse = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(30),
            MaxValueValidator(200)
        ],
        verbose_name='Tętno',
        help_text='uderzeń/min (30-200)'
    )
    
    # Obwody
    waist_circumference = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(30.0),
            MaxValueValidator(200.0)
        ],
        verbose_name='Obwód talii',
        help_text='cm (30.0-200.0)'
    )
    
    hip_circumference = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(50.0),
            MaxValueValidator(200.0)
        ],
        verbose_name='Obwód bioder',
        help_text='cm (50.0-200.0)'
    )
    
    # BMI - opcjonalnie obliczane
    bmi = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='BMI',
        help_text='Opcjonalnie obliczane (kg/m²)'
    )
    
    comments = models.TextField(
        blank=True,
        null=True,
        verbose_name='Komentarze'
    )
    
    measured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='measured_measurements',
        verbose_name='Wykonał pomiar'
    )
    
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entered_measurements',
        verbose_name='Wprowadził dane'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data utworzenia'
    )
    
    class Meta:
        db_table = 'tenant_schema_measurements'
        verbose_name = 'Pomiar'
        verbose_name_plural = 'Pomiary'
        ordering = ['-measurement_date', '-created_at']
    
    def __str__(self):
        return f"Pomiary {self.visit_card.patient.get_decrypted_full_name()} - {self.measurement_date}"
    
    @property
    def blood_pressure_display(self):
        """Wyświetla ciśnienie w formacie 120/80"""
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return None
    
    @property
    def waist_hip_ratio(self):
        """Oblicza stosunek talia/biodra (WHR)"""
        if self.waist_circumference and self.hip_circumference:
            return round(float(self.waist_circumference) / float(self.hip_circumference), 2)
        return None
    
    @property
    def blood_pressure_category(self):
        """Kategoryzuje ciśnienie krwi"""
        if not (self.blood_pressure_systolic and self.blood_pressure_diastolic):
            return None
        
        systolic = self.blood_pressure_systolic
        diastolic = self.blood_pressure_diastolic
        
        if systolic < 120 and diastolic < 80:
            return "Optymalne"
        elif systolic < 130 and diastolic < 85:
            return "Prawidłowe"
        elif systolic < 140 and diastolic < 90:
            return "Wysokie prawidłowe"
        elif systolic < 160 and diastolic < 100:
            return "Nadciśnienie 1 stopnia"
        elif systolic < 180 and diastolic < 110:
            return "Nadciśnienie 2 stopnia"
        else:
            return "Nadciśnienie 3 stopnia"
    
    @property
    def bmi_category(self):
        """Kategoryzuje BMI"""
        if not self.bmi:
            return None
        
        bmi_value = float(self.bmi)
        
        if bmi_value < 18.5:
            return "Niedowaga"
        elif bmi_value < 25:
            return "Prawidłowa masa ciała"
        elif bmi_value < 30:
            return "Nadwaga"
        elif bmi_value < 35:
            return "Otyłość I stopnia"
        elif bmi_value < 40:
            return "Otyłość II stopnia"
        else:
            return "Otyłość III stopnia"
    
    def clean(self):
        """Walidacja modelu"""
        super().clean()
        
        # Sprawdź czy ciśnienie skurczowe > rozkurczowe
        if (self.blood_pressure_systolic and self.blood_pressure_diastolic and 
            self.blood_pressure_systolic <= self.blood_pressure_diastolic):
            raise ValidationError(
                'Ciśnienie skurczowe musi być wyższe niż rozkurczowe'
            )
        
        # Sprawdź czy data pomiaru nie jest z przyszłości
        if self.measurement_date > timezone.now().date():
            raise ValidationError(
                'Data pomiaru nie może być z przyszłości'
            )