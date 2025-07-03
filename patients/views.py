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


class PatientListView(ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        
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
        sort = self.request.GET.get('sort', '')
        if sort and sort in ['name', '-name', 'pesel', '-pesel']:
            # Pobierz wszystkie rekordy i sortuj w Pythonie
            patients_list = list(qs)
            
            if sort in ['name', '-name']:
                # Sortowanie po imieniu i nazwisku
                patients_list.sort(
                    key=lambda p: p.get_decrypted_full_name().lower(),
                    reverse=sort.startswith('-')
                )
            elif sort in ['pesel', '-pesel']:
                # Sortowanie po PESEL
                patients_list.sort(
                    key=lambda p: p.get_decrypted_pesel(),
                    reverse=sort.startswith('-')
                )
            
            # Konwertuj z powrotem na QuerySet używając listy ID
            patient_ids = [p.id for p in patients_list]
            # Zachowaj oryginalną kolejność używając CASE WHEN
            ordering = models.Case(
                *[models.When(id=pid, then=models.Value(i)) for i, pid in enumerate(patient_ids)]
            )
            qs = qs.filter(id__in=patient_ids).order_by(ordering)
            
        elif sort:
            # Standardowe sortowanie dla niezaszyfrowanych pól
            if sort.startswith('-'):
                direction = '-'
                sort_field = sort[1:]
            else:
                direction = ''
                sort_field = sort
            
            sort_mapping = {
                'dob': 'date_of_birth',
                'age': 'date_of_birth',
                'email': 'email',
                'phone': 'phone',
            }
            
            if sort_field in sort_mapping:
                db_field = sort_mapping[sort_field]
                if sort_field == 'age':
                    direction = '-' if direction == '' else ''
                qs = qs.order_by(f"{direction}{db_field}")
            else:
                qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')
            
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['sort'] = self.request.GET.get('sort', '')
        return ctx

    def get_template_names(self):
        # Jeśli to request HTMX, zwróć tylko fragment tabeli
        if self.request.htmx:
            return ['patients/patient_table.html']
        return ['patients/patient_list.html']


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
        
        context.update({
            'page_title': f'Pacjent: {patient.get_decrypted_full_name()}',
            'can_start_40plus': patient.can_start_40plus_visit,
            'current_visit_40plus': current_visit_40plus,
            'visit_40plus_status': visit_40plus_status,
            'visit_count': patient.visit_cards.count(),
            'last_visit': patient.visit_cards.order_by('-created_at').first(),
        })
        
        return context


class PatientCreateView(LoginRequiredMixin, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'
    
    def get_success_url(self):
        return reverse_lazy('patients:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Dodaj nowego pacjenta',
            'breadcrumbs': [
                {'name': 'Pacjenci', 'url': 'patients:list'},
                {'name': 'Dodaj pacjenta', 'url': None}
            ],
            'form_action': 'create'
        })
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f'Pacjent {self.object.get_decrypted_full_name()} został dodany pomyślnie.'
        )
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Wystąpiły błędy w formularzu. Sprawdź wprowadzone dane.'
        )
        return super().form_invalid(form)


class PatientUpdateView(LoginRequiredMixin, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'
    
    def get_success_url(self):
        return reverse_lazy('patients:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.get_object()
        context.update({
            'page_title': f'Edytuj: {patient.get_decrypted_full_name()}',
            'breadcrumbs': [
                {'name': 'Pacjenci', 'url': 'patients:list'},
                {'name': patient.get_decrypted_full_name(), 'url': 'patients:detail', 'url_kwargs': {'pk': patient.pk}},
                {'name': 'Edytuj', 'url': None}
            ],
            'form_action': 'edit'
        })
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f'Dane pacjenta {self.object.get_decrypted_full_name()} zostały zaktualizowane.'
        )
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Wystąpiły błędy w formularzu. Sprawdź wprowadzone dane.'
        )
        return super().form_invalid(form)
    

@require_http_methods(["POST"])
@login_required
def start_40plus_visit(request, pk):
    """Rozpoczyna wizytę 40+ dla pacjenta"""
    patient = get_object_or_404(Patient, pk=pk)
    
    # Sprawdź czy może rozpocząć wizytę 40+
    if not patient.can_start_40plus_visit:
        messages.error(request, "Pacjent nie może obecnie przystąpić do wizyty 40+")
        return redirect('patients:detail', pk=pk)
    
    try:
        # Pobierz typ wizyty 40+
        visit_type_40plus = VisitType.objects.get(name='40+')
        visit_card = VisitCard.objects.create(
            patient=patient,
            visit_type=visit_type_40plus,
            visit_status='oczekiwanie',  
            current_responsible_person=request.user
        )
        
        messages.success(
            request, 
            f"Wizyta 40+ została utworzona dla pacjenta {patient.get_decrypted_full_name()}"
        )
        
    except VisitType.DoesNotExist:
        messages.error(request, "Nie znaleziono typu wizyty 40+")
    except Exception as e:
        messages.error(request, f"Błąd podczas tworzenia wizyty: {str(e)}")
    
    return redirect('patients:detail', pk=pk)