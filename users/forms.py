# users/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'input', 
            'placeholder': 'Nazwa użytkownika'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input', 
            'placeholder': 'Hasło'
        })
    )

    error_messages = {
        'invalid_login': (
            "Nieprawidłowa nazwa użytkownika lub hasło. "
            "Spróbuj ponownie."
        ),
        'inactive': ("Twoje konto jest zablokowane. Skontaktuj się z administratorem."),
    }
