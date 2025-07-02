from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from .models import Patient
from .forms import PatientForm

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
        if sort:
            if sort.startswith('-'):
                direction = '-'
                sort_field = sort[1:]
            else:
                direction = ''
                sort_field = sort
            
            # Mapowanie pól sortowania na rzeczywiste pola bazy danych
            sort_mapping = {
                'dob': 'date_of_birth',
                'age': 'date_of_birth',  # sortowanie po dacie urodzenia dla wieku
                'email': 'email',
                'phone': 'phone',
            }
            
            if sort_field in sort_mapping:
                db_field = sort_mapping[sort_field]
                # Dla wieku odwracamy kierunek (starsze daty = większy wiek)
                if sort_field == 'age':
                    direction = '-' if direction == '' else ''
                qs = qs.order_by(f"{direction}{db_field}")
            else:
                # Dla name i pesel używamy domyślnego sortowania
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
        
        # Dodatkowe dane kontekstowe
        context.update({
            'page_title': f'Pacjent: {patient.get_decrypted_full_name()}',
            'breadcrumbs': [
                {'name': 'Pacjenci', 'url': 'patients:list'},
                {'name': patient.get_decrypted_full_name(), 'url': None}
            ],
            # Dodaj statystyki pacjenta jeśli potrzebne
            'visit_count': patient.visit_cards.count() if hasattr(patient, 'visit_cards') else 0,
            'last_visit': patient.visit_cards.order_by('-created_at').first() if hasattr(patient, 'visit_cards') else None,
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