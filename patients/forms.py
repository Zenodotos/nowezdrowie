from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Patient

class PatientForm(forms.ModelForm):
   

    class Meta:
        model = Patient
        fields = [
            'pesel_encrypted',
            'first_name_encrypted',
            'last_name_encrypted',
            'email',
            'phone',
            'date_of_birth',
        ]
        widgets = {
            'pesel_encrypted': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'PESEL (11 cyfr)',
                'autocomplete': 'off',
            }),
            'first_name_encrypted': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Imię',
                'autocomplete': 'off',
            }),
            'last_name_encrypted': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Nazwisko',
                'autocomplete': 'off',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Email',
                'autocomplete': 'off',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Telefon',
                'autocomplete': 'off',
            }),
        }

    def clean_pesel_encrypted(self):
        pesel = self.cleaned_data.get('pesel_encrypted')
        if pesel in (None, ''):
            raise ValidationError("Pole PESEL jest wymagane.")
        if not pesel.isdigit() or len(pesel) != 11:
            raise ValidationError("PESEL musi składać się z 11 cyfr.")
        return pesel

