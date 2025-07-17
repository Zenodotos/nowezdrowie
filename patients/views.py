from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from .models import Patient
from .forms import PatientForm
from django.db import models
from django.http import JsonResponse
from visits.models import VisitCard, VisitType
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ewus.utils.ewus_client import EWUSClient


class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        gender_filters = self.request.GET.getlist('gender')
        
        # Filtrowanie po płci
        if gender_filters:
            qs = qs.filter(gender__in=gender_filters)
        
        if q:
            # Dla zaszyfrowanych danych musimy przeszukać wszystkie rekordy
            # i filtrować w Pythonie (nieoptymalne, ale konieczne dla zaszyfrowanych danych)
            matching_ids = []
            for patient in qs:
                try:
                    # Sprawdzaj czy szukany tekst jest w imieniu, nazwisku lub PESEL
                    full_name = patient.get_decrypted_full_name().lower()
                    pesel = patient.get_decrypted_pesel()
                    
                    if (q.lower() in full_name or 
                        q in pesel or 
                        q.replace(' ', '') in pesel.replace(' ', '')):
                        matching_ids.append(patient.id)
                except:
                    # Jeśli nie można odszyfrować, pomiń
                    continue
            
            qs = qs.filter(id__in=matching_ids)

        # Sortowanie - używamy domyślnego sortowania z bazy danych
        sort = self.request.GET.get('sort', '').strip()
        if sort:
            # Mapowanie sortowania (bo nie możemy sortować po zaszyfrowanych polach)
            if sort in ['name', '-name', 'pesel', '-pesel', 'email', '-email']:
                # Te pola są zaszyfrowane, więc sortujemy w Pythonie
                patients_list = list(qs)
                if sort == 'name':
                    patients_list.sort(key=lambda p: p.get_decrypted_full_name().lower())
                elif sort == '-name':
                    patients_list.sort(key=lambda p: p.get_decrypted_full_name().lower(), reverse=True)
                elif sort == 'pesel':
                    patients_list.sort(key=lambda p: p.get_decrypted_pesel())
                elif sort == '-pesel':
                    patients_list.sort(key=lambda p: p.get_decrypted_pesel(), reverse=True)
                elif sort == 'email':
                    patients_list.sort(key=lambda p: p.get_decrypted_email().lower())
                elif sort == '-email':
                    patients_list.sort(key=lambda p: p.get_decrypted_email().lower(), reverse=True)
                return patients_list
            elif sort in ['date_of_birth', '-date_of_birth', 'age', '-age']:
                # Te pola można sortować normalnie
                if sort == 'age':
                    qs = qs.order_by('date_of_birth')  # młodsi = nowsza data urodzenia
                elif sort == '-age':
                    qs = qs.order_by('-date_of_birth')  # starsi = starsza data urodzenia
                else:
                    qs = qs.order_by(sort)
            else:
                qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')
            
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['sort'] = self.request.GET.get('sort', '')
        ctx['gender_filters'] = self.request.GET.getlist('gender')
        return ctx


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.get_object()
        
        # Sprawdź wizytę 40+
        current_visit_40plus = patient.current_40plus_visit
        
        visit_40plus_status = None
        if current_visit_40plus:
            visit_40plus_status = {
                'has_questionnaire': current_visit_40plus.questionnaire_date is not None,
                'has_examinations': current_visit_40plus.examinations.filter(status='completed').exists(),
                'has_measurements': current_visit_40plus.measurements.exists(),
                'can_refer_to_ipz': (
                    current_visit_40plus.examinations.filter(status='completed').exists() and 
                    current_visit_40plus.measurements.exists()
                ),
                'visit_card': current_visit_40plus
            }
        
        # Sprawdź ubezpieczenie TYLKO gdy refresh=1
        insurance_info = None
        if self.request.GET.get('refresh') == '1':
            insurance_info = self._check_insurance(patient)
        else:
            insurance_info = {
                'status': 'not_checked',
                'message': 'Kliknij "Sprawdź ubezpieczenie" aby zaktualizować dane'
            }
        
        context.update({
            'page_title': f'Pacjent: {patient.get_decrypted_full_name()}',
            'recent_visits': patient.visit_cards.all().order_by('-created_at')[:5],
            'visit_40plus_status': visit_40plus_status,
            'insurance_info': insurance_info,
        })
        return context
    
    def _check_insurance(self, patient):
        """Sprawdza ubezpieczenie pacjenta"""
        if not self.request.session.get('ewus_session'):
            return {
                'status': 'no_session',
                'message': 'Brak sesji eWUS',
                'badge_class': 'badge-warning',
                'icon': '⚠️'
            }
        
        try:
            from ewus.utils.ewus_client import EWUSClient, InsuranceStatus
            client = EWUSClient(test_environment=True, debug=False)
            print(self.request.session['ewus_session'])
            client.restore_session(self.request.session['ewus_session'])
            
            pesel = patient.get_decrypted_pesel()
            result = client.check_insurance(pesel)
            
            if result.patient.insurance_status == InsuranceStatus.AKTYWNY:
                return {
                    'status': 'active',
                    'message': 'Ubezpieczenie aktywne',
                    'badge_class': 'badge-success',
                    'icon': '✅',
                    'details': result
                }
            elif result.patient.insurance_status == InsuranceStatus.NIEAKTYWNY:
                return {
                    'status': 'inactive',
                    'message': 'Ubezpieczenie nieaktywne',
                    'badge_class': 'badge-error',
                    'icon': '❌',
                    'details': result
                }
            else:
                return {
                    'status': 'unknown',
                    'message': 'Status nieznany',
                    'badge_class': 'badge-warning',
                    'icon': '⚠️',
                    'details': result
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Błąd sprawdzania ubezpieczenia: {str(e)}",
                'badge_class': 'badge-error',
                'icon': '❌'
            }


class PatientCreateView(LoginRequiredMixin, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Dodaj nowego pacjenta'
        context['form_title'] = 'Nowy pacjent'
        context['submit_text'] = 'Dodaj pacjenta'
        return context
        
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f'Pacjent {self.object.get_decrypted_full_name()} został pomyślnie dodany.'
        )
        return response
    
    def get_success_url(self):
        return reverse_lazy('patients:detail', kwargs={'pk': self.object.pk})


class PatientUpdateView(LoginRequiredMixin, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Edycja: {self.object.get_decrypted_full_name()}'
        context['form_title'] = f'Edytuj dane pacjenta'
        context['submit_text'] = 'Zapisz zmiany'
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Dane pacjenta {self.object.get_decrypted_full_name()} zostały zaktualizowane.'
        )
        return response
    
    def get_success_url(self):
        return reverse_lazy('patients:detail', kwargs={'pk': self.object.pk})


@login_required
@require_http_methods(["POST"])  
def create_visit_40plus(request, patient_id):
    """Tworzy nową wizytę 40+ dla pacjenta"""
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Sprawdź czy pacjent ma już aktywną wizytę 40+
        if patient.current_40plus_visit:
            return JsonResponse({
                'success': False,
                'error': 'Pacjent ma już aktywną wizytę 40+. Zakończ poprzednią wizytę przed utworzeniem nowej.'
            }, status=400)
        
        # Pobierz typ wizyty 40+
        visit_type_40plus = VisitType.objects.filter(name__icontains='40+').first()
        if not visit_type_40plus:
            return JsonResponse({
                'success': False,
                'error': 'Nie znaleziono typu wizyty 40+ w systemie. Skontaktuj się z administratorem.'
            }, status=400)
        
        # Utwórz nową kartę wizyty
        visit_card = VisitCard.objects.create(
            patient=patient,
            visit_type=visit_type_40plus.name,
            visit_status='oczekiwanie',
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'visit_card_id': visit_card.id,
            'message': f'Wizyta 40+ została utworzona dla pacjenta {patient.get_decrypted_full_name()}',
            'redirect_url': f'/wizyty/{visit_card.id}/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Błąd podczas tworzenia wizyty: {str(e)}'
        }, status=500)