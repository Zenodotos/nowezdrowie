from django import forms
from .models import Patient


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            'first_name_encrypted',
            'last_name_encrypted', 
            'pesel_encrypted',
            'email',
            'phone',
        ]
        
        widgets = {
            'first_name_encrypted': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Wprowadź imię pacjenta',
                'required': True
            }),
            'last_name_encrypted': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Wprowadź nazwisko pacjenta',
                'required': True
            }),
            'pesel_encrypted': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Wprowadź PESEL (11 cyfr)',
                'maxlength': '11',
                'pattern': '[0-9]{11}',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'email@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': '+48 123 456 789'
            }),
        }
        
        labels = {
            'first_name_encrypted': 'Imię',
            'last_name_encrypted': 'Nazwisko',
            'pesel_encrypted': 'PESEL',
            'email': 'Adres email',
            'phone': 'Telefon',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Jeśli to edycja, ustaw wartości z odszyfrowanych danych
        if self.instance and self.instance.pk:
            try:
                self.initial['first_name_encrypted'] = self.instance.first_name_encrypted
                self.initial['last_name_encrypted'] = self.instance.last_name_encrypted
                self.initial['pesel_encrypted'] = self.instance.pesel_encrypted
            except:
                pass
    
    def clean_pesel_encrypted(self):
        pesel = self.cleaned_data.get('pesel_encrypted')
        if pesel:
            # Usuwamy spacje i myślniki
            pesel = pesel.replace(' ', '').replace('-', '')
            
            # Sprawdzamy czy to 11 cyfr
            if not pesel.isdigit() or len(pesel) != 11:
                raise forms.ValidationError('PESEL musi składać się z 11 cyfr.')
            
            # Używamy walidacji z modelu Patient
            try:
                Patient.validate_pesel(pesel)
            except Exception as e:
                raise forms.ValidationError(str(e))
            
            # Sprawdź czy PESEL już istnieje (tylko dla nowych pacjentów lub zmiany PESEL)
            existing_patient = Patient.objects.search_by_pesel(pesel).first()
            if existing_patient and existing_patient != self.instance:
                raise forms.ValidationError('Pacjent z tym numerem PESEL już istnieje w systemie.')
                
        return pesel

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Sprawdzenie czy email nie jest już zajęty (z wyłączeniem bieżącego pacjenta)
            existing_patient = Patient.objects.filter(email=email)
            if self.instance.pk:
                existing_patient = existing_patient.exclude(pk=self.instance.pk)
            if existing_patient.exists():
                raise forms.ValidationError('Pacjent z tym adresem email już istnieje.')
        return email