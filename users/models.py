from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = [
        ('profilaktyk', 'Profilaktyk'),
        ('pielęgniarka', 'Pielęgniarka'),
        ('lekarz', 'Lekarz'),
        ('koordynator', 'Koordynator'),
        ('dietetyk', 'Dietetyk'),
        ('pacjent', 'Pacjent'),
    ]
    
    phone = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        verbose_name='Numer telefonu użytkownika'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        blank=True,
        null=True
    )

    email = models.EmailField(
        unique=True,
        blank=False,
        null=False
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Użytkownik'
        verbose_name_plural = 'Użytkownicy'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
