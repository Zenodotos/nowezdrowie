from django.shortcuts import render
from .models import Patient

def find_patient(request):
    patients = Patient.objects.all()
    context = {'patients': patients}
    return render(request, 'patients/patient.html', context)