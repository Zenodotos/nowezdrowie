from django.views.generic import ListView, CreateView
from django.http import HttpResponse
from django.template.loader import render_to_string
from .models import Patient
from .forms import PatientForm

class PatientListView(ListView):
    model = Patient
    context_object_name = 'patients'
    template_name = 'patients/patient_list.html'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q') or self.request.GET.get('pesel_encrypted')
        if q:
            # wyszukiwanie po pełnym imieniu/nazwisku lub PESEL
            qs = Patient.objects.search_by_full_name(q) | Patient.objects.search_by_pesel(q)
        return qs.order_by('-created_at')

    def render_to_response(self, context, **response_kwargs):
        if self.request.htmx:
            # gdy to żądanie HTMX, zwracamy tylko fragment z listą
            html = render_to_string('patients/partials/patient_list.html', context, request=self.request)
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)


class PatientCreateView(CreateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'

    def form_valid(self, form):
        obj = form.save()
        if self.request.htmx:
            # po udanym zapisie: odśwież listę pacjentów
            patients = Patient.objects.order_by('-created_at')[:25]
            html = render_to_string('patients/partials/patient_list.html', {'patients': patients}, request=self.request)
            return HttpResponse(html, headers={
                'HX-Trigger': 'patientListChanged'
            })
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.htmx:
            return HttpResponse(
                render_to_string('patients/partials/patient_form.html', {'form': form}, request=self.request),
                status=400
            )
        return super().form_invalid(form)
