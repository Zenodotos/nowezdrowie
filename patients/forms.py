from django import forms
from .models import Patient

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['pesel_encrypted', 'first_name_encrypted', 'last_name_encrypted', 'email', 'phone']
        widgets = {
            'pesel_encrypted': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'PESEL',
                'hx-trigger': 'keyup changed delay:500ms',
                'hx-get': "{% url 'patients:list' %}",
                'hx-target': '#patient-list',
                'hx-include': '[name=pesel_encrypted]',
            }),
            'first_name_encrypted': forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Imię'}),
            'last_name_encrypted': forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Nazwisko'}),
            'email': forms.EmailInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Telefon'}),
        }
