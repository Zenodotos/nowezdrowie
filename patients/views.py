from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.contrib import messages
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
        'email': ['email'],
        'phone': ['phone'],
    }

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        if q:
            ids = [p.id for p in qs if q in p.get_decrypted_pesel() or q.lower() in p.get_decrypted_full_name().lower()]
            qs = qs.filter(id__in=ids)
        # sortowanie domyślne
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


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['sort'] = self.request.GET.get('sort', '')
        return ctx
    

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