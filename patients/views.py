from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from .models import Patient
from .forms import PatientForm


class PatientListView(ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 25

    # definiujemy pola sortowania
    SORT_FIELDS = {
        'name': ['first_name_encrypted', 'last_name_encrypted'],
        'pesel': ['pesel_encrypted'],
        'dob': ['date_of_birth'],
        'age': ['date_of_birth'],  # starsze daty -> większy wiek
        'gender': ['gender'],
        'email': ['email'],
        'phone': ['phone'],
    }

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        if q:
            # To może być powolne dla dużych baz danych, ale zachowujemy obecną logikę
            ids = []
            for p in qs:
                try:
                    pesel = p.get_decrypted_pesel()
                    name = p.get_decrypted_full_name().lower()
                    if q in pesel or q.lower() in name:
                        ids.append(p.id)
                except:
                    # W przypadku błędów odszyfrowania, pomijamy ten rekord
                    continue
            qs = qs.filter(id__in=ids)
        
        # sortowanie
        sort = self.request.GET.get('sort', '')
        direction = ''
        if sort.startswith('-'):
            direction = '-'
            sort = sort[1:]
        if sort in self.SORT_FIELDS:
            order = [f"{direction}{f}" for f in self.SORT_FIELDS[sort]]
            return qs.order_by(*order)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['sort'] = self.request.GET.get('sort', '')
        return ctx

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        
        # Jeśli to HTMX request, zwracamy tylko tabelę
        if request.headers.get('HX-Request'):
            html = render_to_string('patients/patient_table.html', context, request=request)
            return HttpResponse(html)
        
        # Inaczej zwracamy pełną stronę
        return self.render_to_response(context)


class PatientCreateView(CreateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'
    success_url = reverse_lazy('patients:list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Pacjent został dodany.')
        return response

    def form_invalid(self, form):
        # by messages nie nadpisywały alertów w szablonie, po prostu renderujemy z błędami
        return super().form_invalid(form)