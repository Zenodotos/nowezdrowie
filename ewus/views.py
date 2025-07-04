from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ewus.utils.ewus_client import EWUSClient   
from django.http import HttpResponse
import json



# views.py - sesja dla całej zmiany
@login_required
def start_ewus_session(request):
    """Logowanie do eWUS na początek dnia"""
    client = EWUSClient(test_environment=True)
    credentials = EWUSClient.create_doctor_credentials(
        domain="15",
        login="TEST1", 
        password="qwerty!@#"
    )
        
    session_info, status = client.login(credentials)
    
    # Zapisz sesję na cały dzień
    request.session['ewus_session'] = client.save_session_to_dict()
    request.session.set_expiry(8 * 60 * 60)
    return HttpResponse(
        json.dumps(request.session['ewus_session'], ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8'
    )
    
@login_required 
def check_patient(request):
    """Sprawdzenie pojedynczego pacjenta - używa istniejącej sesji"""
    if not request.session.get('ewus_session'):
        return redirect('start_ewus_session')
    
    client = EWUSClient(test_environment=True)
    client.restore_session(request.session['ewus_session'])
    
    # Używaj tej samej sesji dla wielu sprawdzeń
    result = client.check_insurance('00032948271')
    return HttpResponse(result)
    
@login_required
def end_ewus_session(request):
    """Wylogowanie z eWUS na koniec dnia"""
    if request.session.get('ewus_session'):
        client = EWUSClient(test_environment=True)
        client.restore_session(request.session['ewus_session'])
        client.logout()
        del request.session['ewus_session']
    return HttpResponse('wylogowano')