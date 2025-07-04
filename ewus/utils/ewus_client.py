import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid
import re

class OperatorType(Enum):
    """Typy operatorów w systemie eWUS"""
    LEKARZ = "LEK"
    SWIADCZENIODAWCA = "SWD"

class LoginStatus(Enum):
    """Statusy logowania"""
    SUCCESS = "000"
    PASSWORD_EXPIRES_SOON = "001"
    PASSWORD_EXPIRES_TOMORROW = "002"
    PASSWORD_EXPIRES_TODAY = "003"

class InsuranceStatus(Enum):
    """Statusy ubezpieczenia"""
    AKTYWNY = 1
    NIEAKTYWNY = 0
    PESEL_NIEAKTUALNY = -1

@dataclass
class LoginCredentials:
    """Dane do logowania operatora"""
    domain: str  # Kod OW NFZ (01-16)
    login: str
    password: str
    operator_type: Optional[OperatorType] = None
    doctor_id: Optional[str] = None  # idntLek dla lekarzy
    provider_id: Optional[str] = None  # idntSwd dla świadczeniodawców

@dataclass
class SessionInfo:
    """Informacje o sesji"""
    session_id: str
    auth_token: str
    login_time: datetime
    operator_id: str
    ow_code: str
    expires_at: datetime

@dataclass
class PatientInfo:
    """Informacje o pacjencie"""
    pesel: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    insurance_status: Optional[InsuranceStatus] = None
    status_symbol: Optional[str] = None
    expiration_date: Optional[datetime] = None
    additional_info: Optional[List[Dict]] = None

@dataclass
class InsuranceCheckResult:
    """Wynik sprawdzenia ubezpieczenia"""
    operation_id: str
    operation_date: datetime
    patient: PatientInfo
    operator_id: str
    ow_code: str
    provider_id: Optional[str] = None
    is_valid: bool = False
    notes: Optional[List[str]] = None

class EWUSException(Exception):
    """Bazowy wyjątek dla systemu eWUS"""
    pass

class AuthenticationException(EWUSException):
    """Błąd uwierzytelnienia"""
    pass

class AuthorizationException(EWUSException):
    """Błąd autoryzacji"""
    pass

class SessionException(EWUSException):
    """Błąd sesji"""
    pass

class AuthTokenException(EWUSException):
    """Błąd tokenu autoryzacyjnego"""
    pass

class InputException(EWUSException):
    """Błąd danych wejściowych"""
    pass

class ServiceException(EWUSException):
    """Błąd serwisu"""
    pass

class ServerException(EWUSException):
    """Błąd serwera"""
    pass

class PassExpiredException(EWUSException):
    """Hasło wygasło"""
    pass

class EWUSClient:
    """
    Klient systemu eWUS NFZ do sprawdzania statusu ubezpieczenia pacjentów.
    
    Obsługuje:
    - Logowanie lekarzy i świadczeniodawców
    - Sprawdzanie statusu ubezpieczenia
    - Zmianę hasła
    - Zarządzanie sesjami
    """
    
    def __init__(self, test_environment: bool = True, debug: bool = False):
        """
        Inicjalizacja klienta eWUS
        
        Args:
            test_environment: Czy używać środowiska testowego (domyślnie True)
            debug: Czy włączyć tryb debugowania (pokazuje XML i odpowiedzi)
        """
        self.test_environment = test_environment
        self.debug = debug
        self.base_url = self._get_base_url()
        self.auth_url = f"{self.base_url}/services/Auth"
        self.broker_url = f"{self.base_url}/services/ServiceBroker"
        self.session: Optional[SessionInfo] = None
        
        # Dane testowe dla środowiska testowego
        self.test_credentials = {
            "15": {"login": "TEST1", "password": "qwerty!@#"},
            "01": {"login": "TEST1", "password": "qwerty!@#"}
        }
        
        # PESEL-e testowe
        self.test_pesels = {
            "aktywny": "00092497177",  # Dowolny parzysty PESEL
            "szczepienie": "00081314722",  # Ma zaświadczenie o szczepieniu
            "kwarantanna": "00032948271",  # Objęty kwarantanną
            "nieaktualny": "02082642235"  # PESEL nieaktualny
        }
    
    def _get_base_url(self) -> str:
        """
        Zwraca URL bazowy w zależności od środowiska
        
        URL-e zostały wzięte z AuthService.php i BrokerService.php:
        - Testowy: ws-broker-server-ewus-auth-test
        - Produkcyjny: ws-broker-server-ewus (bez 'auth-prod'!)
        """
        if self.test_environment:
            return "https://ewus.nfz.gov.pl/ws-broker-server-ewus-auth-test"
        else:
            # POPRAWIONY URL PRODUKCYJNY na podstawie AuthService.php i BrokerService.php
            return "https://ewus.nfz.gov.pl/ws-broker-server-ewus"
    
    def _get_required_params(self, domain: str, operator_type: OperatorType) -> List[str]:
        """
        Zwraca wymagane parametry logowania dla danej domeny i typu operatora
        
        Args:
            domain: Kod OW NFZ
            operator_type: Typ operatora
            
        Returns:
            Lista wymaganych parametrów
        """
        extended_domains = ["01", "04", "05", "06", "08", "09", "11", "12"]
        simple_domains = ["02", "03", "07", "10", "13", "14", "15", "16"]
        
        base_params = ["domain", "login"]
        
        if domain in extended_domains:
            if operator_type == OperatorType.LEKARZ:
                return base_params + ["type", "idntLek"]
            elif operator_type == OperatorType.SWIADCZENIODAWCA:
                return base_params + ["type", "idntSwd"]
        
        return base_params
    
    def _create_login_xml(self, credentials: LoginCredentials) -> str:
        """
        Tworzy XML do logowania
        
        Args:
            credentials: Dane logowania
            
        Returns:
            XML do wysłania
        """
        required_params = []
        
        if credentials.operator_type:
            required_params = self._get_required_params(
                credentials.domain, 
                credentials.operator_type
            )
        else:
            required_params = ["domain", "login"]
        
        # Budowa parametrów credentials
        items = []
        items.append(f"""
            <auth:item>
                <auth:name>domain</auth:name>
                <auth:value>
                    <auth:stringValue>{credentials.domain}</auth:stringValue>
                </auth:value>
            </auth:item>""")
        
        items.append(f"""
            <auth:item>
                <auth:name>login</auth:name>
                <auth:value>
                    <auth:stringValue>{credentials.login}</auth:stringValue>
                </auth:value>
            </auth:item>""")
        
        if "type" in required_params and credentials.operator_type:
            items.append(f"""
            <auth:item>
                <auth:name>type</auth:name>
                <auth:value>
                    <auth:stringValue>{credentials.operator_type.value}</auth:stringValue>
                </auth:value>
            </auth:item>""")
        
        if "idntLek" in required_params and credentials.doctor_id:
            items.append(f"""
            <auth:item>
                <auth:name>idntLek</auth:name>
                <auth:value>
                    <auth:stringValue>{credentials.doctor_id}</auth:stringValue>
                </auth:value>
            </auth:item>""")
        
        if "idntSwd" in required_params and credentials.provider_id:
            items.append(f"""
            <auth:item>
                <auth:name>idntSwd</auth:name>
                <auth:value>
                    <auth:stringValue>{credentials.provider_id}</auth:stringValue>
                </auth:value>
            </auth:item>""")
        
        credentials_xml = "".join(items)
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:auth="http://xml.kamsoft.pl/ws/kaas/login_types">
    <soapenv:Header/>
    <soapenv:Body>
        <auth:login>
            <auth:credentials>{credentials_xml}
            </auth:credentials>
            <auth:password>{credentials.password}</auth:password>
        </auth:login>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    def _create_check_cwu_xml(self, pesel: str) -> str:
        """
        Tworzy XML do sprawdzenia statusu ubezpieczenia
        
        Args:
            pesel: Numer PESEL pacjenta
            
        Returns:
            XML do wysłania
        """
        if not self.session:
            raise SessionException("Brak aktywnej sesji. Zaloguj się najpierw.")
        
        current_time = datetime.now().isoformat()
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:com="http://xml.kamsoft.pl/ws/common" 
                  xmlns:brok="http://xml.kamsoft.pl/ws/broker">
    <soapenv:Header>
        <com:session id="{self.session.session_id}" xmlns:ns1="http://xml.kamsoft.pl/ws/common"/>
        <com:authToken id="{self.session.auth_token}" xmlns:ns1="http://xml.kamsoft.pl/ws/common"/>
    </soapenv:Header>
    <soapenv:Body>
        <brok:executeService>
            <com:location>
                <com:namespace>nfz.gov.pl/ws/broker/cwu</com:namespace>
                <com:localname>checkCWU</com:localname>
                <com:version>5.0</com:version>
            </com:location>
            <brok:date>{current_time}</brok:date>
            <brok:payload>
                <brok:textload>
                    <ewus:status_cwu_pyt xmlns:ewus="https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5">
                        <ewus:numer_pesel>{pesel}</ewus:numer_pesel>
                        <ewus:system_swiad nazwa="eWUS-Python-Client" wersja="1.0.0"/>
                    </ewus:status_cwu_pyt>
                </brok:textload>
            </brok:payload>
        </brok:executeService>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    def _create_logout_xml(self) -> str:
        """Tworzy XML do wylogowania"""
        if not self.session:
            raise SessionException("Brak aktywnej sesji.")
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:auth="http://xml.kamsoft.pl/ws/kaas/login_types"
                  xmlns:com="http://xml.kamsoft.pl/ws/common">
    <soapenv:Header/>
    <soapenv:Body>
        <auth:logout>
            <com:session id="{self.session.session_id}" xmlns:ns1="http://xml.kamsoft.pl/ws/common"/>
        </auth:logout>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    def _create_change_password_xml(self, credentials: LoginCredentials, 
                                  old_password: str, new_password: str) -> str:
        """
        Tworzy XML do zmiany hasła
        
        Args:
            credentials: Dane logowania
            old_password: Stare hasło
            new_password: Nowe hasło
            
        Returns:
            XML do wysłania
        """
        login_xml_part = self._create_login_xml(credentials)
        # Wyciągamy część credentials z XML logowania
        root = ET.fromstring(login_xml_part)
        credentials_elem = root.find(".//auth:credentials", 
                                   {"auth": "http://xml.kamsoft.pl/ws/kaas/login_types"})
        credentials_xml = ET.tostring(credentials_elem, encoding="unicode")
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:auth="http://xml.kamsoft.pl/ws/kaas/login_types">
    <soapenv:Header/>
    <soapenv:Body>
        <auth:changePassword>
            {credentials_xml}
            <auth:oldPassword>{old_password}</auth:oldPassword>
            <auth:newPassword>{new_password}</auth:newPassword>
            <auth:newPasswordRepeat>{new_password}</auth:newPasswordRepeat>
        </auth:changePassword>
    </soapenv:Body>
</soapenv:Envelope>"""
    
    def _parse_soap_fault(self, response_text: str) -> None:
        """
        Parsuje błędy SOAP i rzuca odpowiednie wyjątki
        
        Args:
            response_text: Odpowiedź SOAP z błędem
        """
        try:
            root = ET.fromstring(response_text)
            
            # Sprawdź błędy NFZ (com:faultcode)
            fault_code_nfz = root.find(".//com:faultcode", {"com": "http://xml.kamsoft.pl/ws/common"})
            fault_string_nfz = root.find(".//com:faultstring", {"com": "http://xml.kamsoft.pl/ws/common"})
            
            if fault_code_nfz is not None and fault_string_nfz is not None:
                code = fault_code_nfz.text
                message = fault_string_nfz.text
                
                # Wyciągnij typ błędu z faultcode (np. "Client.AuthenticationException" -> "AuthenticationException")
                if "." in code:
                    error_type = code.split(".")[-1]
                else:
                    error_type = code
                
                if "AuthenticationException" in error_type:
                    raise AuthenticationException(message)
                elif "AuthorizationException" in error_type:
                    raise AuthorizationException(message)
                elif "SessionException" in error_type:
                    raise SessionException(message)
                elif "AuthTokenException" in error_type:
                    raise AuthTokenException(message)
                elif "InputException" in error_type:
                    raise InputException(message)
                elif "ServiceException" in error_type:
                    raise ServiceException(message)
                elif "ServerException" in error_type:
                    raise ServerException(message)
                elif "PassExpiredException" in error_type:
                    raise PassExpiredException(message)
                else:
                    raise EWUSException(f"Nieznany błąd NFZ: {code} - {message}")
            
            # Sprawdź standardowe błędy SOAP
            fault = root.find(".//soap:Fault", {"soap": "http://schemas.xmlsoap.org/soap/envelope/"})
            if fault is None:
                fault = root.find(".//soapenv:Fault", {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/"})
            
            if fault is not None:
                fault_code = fault.find("faultcode")
                fault_string = fault.find("faultstring")
                
                if fault_code is not None and fault_string is not None:
                    code = fault_code.text
                    message = fault_string.text
                    raise EWUSException(f"Błąd SOAP: {code} - {message}")
            
            # Jeśli nie znaleziono fault, ale mamy response_text, pokaż co było
            if response_text.strip():
                raise EWUSException(f"Nieoczekiwana odpowiedź serwera: {response_text[:500]}...")
            else:
                raise EWUSException("Pusta odpowiedź serwera")
                
        except ET.ParseError as e:
            raise EWUSException(f"Nie można sparsować odpowiedzi XML: {str(e)[:200]}... Odpowiedź: {response_text[:300]}...")
    
    def _simulate_login_response(self, credentials: LoginCredentials) -> SessionInfo:
        """
        Symuluje odpowiedź logowania w środowisku testowym
        
        Args:
            credentials: Dane logowania
            
        Returns:
            Informacje o sesji
        """
        if not self.test_environment:
            raise EWUSException("Symulacja dostępna tylko w środowisku testowym")
        
        # Sprawdzenie czy dane testowe są poprawne
        test_data = self.test_credentials.get(credentials.domain)
        if not test_data or test_data["login"] != credentials.login or test_data["password"] != credentials.password:
            raise AuthenticationException("Nieprawidłowe dane logowania")
        
        session_id = str(uuid.uuid4()).replace("-", "")
        auth_token = str(uuid.uuid4()).replace("-", "")
        
        return SessionInfo(
            session_id=session_id,
            auth_token=auth_token,
            login_time=datetime.now(),
            operator_id="TEST123",
            ow_code=credentials.domain,
            expires_at=datetime.now() + timedelta(hours=8)
        )
    
    def _simulate_check_response(self, pesel: str) -> InsuranceCheckResult:
        """
        Symuluje odpowiedź sprawdzenia ubezpieczenia w środowisku testowym
        
        Args:
            pesel: Numer PESEL
            
        Returns:
            Wynik sprawdzenia ubezpieczenia
        """
        if not self.test_environment:
            raise EWUSException("Symulacja dostępna tylko w środowisku testowym")
        
        operation_id = str(uuid.uuid4()).replace("-", "")[:20]
        
        # Sprawdzenie czy PESEL jest w danych testowych
        patient = PatientInfo(pesel=pesel)
        
        if pesel == self.test_pesels["aktywny"] or pesel.isdigit() and int(pesel[-1]) % 2 == 0:
            # Parzysty PESEL = aktywny
            patient.insurance_status = InsuranceStatus.AKTYWNY
            patient.first_name = "Jan"
            patient.last_name = "Kowalski"
            patient.status_symbol = "DN"
            patient.expiration_date = datetime.now() + timedelta(days=30)
            is_valid = True
            notes = ["Pacjent ma aktywne ubezpieczenie"]
            
        elif pesel == self.test_pesels["szczepienie"]:
            # Ma zaświadczenie o szczepieniu
            patient.insurance_status = InsuranceStatus.AKTYWNY
            patient.first_name = "Anna"
            patient.last_name = "Nowak"
            patient.status_symbol = "DN"
            patient.expiration_date = datetime.now() + timedelta(days=30)
            patient.additional_info = [
                {"kod": "ZASWIADCZENIE-COVID", "poziom": "I", 
                 "wartosc": "Pacjent posiada zaświadczenie o szczepieniu COVID-19"}
            ]
            is_valid = True
            notes = ["Pacjent ma aktywne ubezpieczenie", "Posiada zaświadczenie o szczepieniu COVID-19"]
            
        elif pesel == self.test_pesels["kwarantanna"]:
            # Objęty kwarantanną
            patient.insurance_status = InsuranceStatus.AKTYWNY
            patient.first_name = "Piotr"
            patient.last_name = "Wiśniewski"
            patient.status_symbol = "DN"
            patient.expiration_date = datetime.now() + timedelta(days=30)
            patient.additional_info = [
                {"kod": "KWARANTANNA-COVID19", "poziom": "O", 
                 "wartosc": "Pacjent objęty kwarantanną COVID-19"}
            ]
            is_valid = True
            notes = ["Pacjent ma aktywne ubezpieczenie", "Objęty kwarantanną COVID-19"]
            
        elif pesel == self.test_pesels["nieaktualny"]:
            # PESEL nieaktualny
            patient.insurance_status = InsuranceStatus.PESEL_NIEAKTUALNY
            is_valid = False
            notes = ["PESEL nieaktualny - anulowany przez MSW"]
            
        else:
            # Nieparzysty PESEL = brak ubezpieczenia
            patient.insurance_status = InsuranceStatus.NIEAKTYWNY
            is_valid = False
            notes = ["Brak aktywnego ubezpieczenia"]
        
        return InsuranceCheckResult(
            operation_id=operation_id,
            operation_date=datetime.now(),
            patient=patient,
            operator_id=self.session.operator_id,
            ow_code=self.session.ow_code,
            is_valid=is_valid,
            notes=notes
        )
    
    def login(self, credentials: LoginCredentials) -> Tuple[SessionInfo, LoginStatus]:
        """
        Loguje operatora do systemu eWUS
        
        Args:
            credentials: Dane logowania
            
        Returns:
            Tuple zawierający informacje o sesji i status logowania
        """
        try:
            if self.test_environment:
                # W środowisku testowym symulujemy logowanie
                session_info = self._simulate_login_response(credentials)
                self.session = session_info
                return session_info, LoginStatus.SUCCESS
            
            # W środowisku produkcyjnym wyślij prawdziwe żądanie SOAP
            xml_request = self._create_login_xml(credentials)
            
            if self.debug:
                print("🔧 DEBUG - Wysyłany XML:")
                print(xml_request)
                print("🔧 DEBUG - URL:", self.auth_url)
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://xml.kamsoft.pl/ws/auth/Auth/loginRequest'
            }
            
            if self.debug:
                print("🔧 DEBUG - Nagłówki:", headers)
            
            response = requests.post(self.auth_url, data=xml_request, headers=headers)
            
            if self.debug:
                print("🔧 DEBUG - Status kod:", response.status_code)
                print("🔧 DEBUG - Odpowiedź:")
                print(response.text)
            
            if response.status_code != 200:
                # Sprawdź czy to błąd SOAP czy HTTP
                if response.status_code == 500:
                    # Błąd 500 może zawierać SOAP fault
                    self._parse_soap_fault(response.text)
                else:
                    raise EWUSException(f"Błąd HTTP {response.status_code}: {response.text[:300]}...")
            
            # Parsowanie odpowiedzi (implementacja dla środowiska produkcyjnego)
            # ... kod parsowania odpowiedzi SOAP ...
            
            raise NotImplementedError("Środowisko produkcyjne nie jest jeszcze zaimplementowane")
            
        except Exception as e:
            if isinstance(e, EWUSException):
                raise
            raise EWUSException(f"Błąd podczas logowania: {str(e)}")
    
    def check_insurance(self, pesel: str) -> InsuranceCheckResult:
        """
        Sprawdza status ubezpieczenia pacjenta
        
        Args:
            pesel: Numer PESEL pacjenta
            
        Returns:
            Wynik sprawdzenia ubezpieczenia
        """
        if not self.session:
            raise SessionException("Brak aktywnej sesji. Zaloguj się najpierw.")
        
        # Walidacja PESEL
        if not self._validate_pesel(pesel):
            raise InputException("Nieprawidłowy format numeru PESEL")
        
        try:
            if self.test_environment:
                return self._simulate_check_response(pesel)
            
            # W środowisku produkcyjnym wyślij prawdziwe żądanie
            xml_request = self._create_check_cwu_xml(pesel)
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'executeService'
            }
            
            response = requests.post(self.broker_url, data=xml_request, headers=headers)
            
            if response.status_code != 200:
                raise EWUSException(f"Błąd HTTP: {response.status_code}")
            
            # Parsowanie odpowiedzi (implementacja dla środowiska produkcyjnego)
            raise NotImplementedError("Środowisko produkcyjne nie jest jeszcze zaimplementowane")
            
        except Exception as e:
            if isinstance(e, EWUSException):
                raise
            raise EWUSException(f"Błąd podczas sprawdzania ubezpieczenia: {str(e)}")
    def save_session_to_dict(self) -> dict:
        """Zapisuje sesję do słownika dla Django session"""
        if not self.session:
            return {}
        
        return {
            'session_id': self.session.session_id,
            'auth_token': self.session.auth_token,
            'login_time': self.session.login_time.isoformat(),
            'operator_id': self.session.operator_id,
            'ow_code': self.session.ow_code,
            'expires_at': self.session.expires_at.isoformat()
        }
    
    def restore_session(self, session_dict: dict) -> bool:
        """Odtwarza sesję ze słownika Django session"""
        if not session_dict:
            return False
        
        try:
            self.session = SessionInfo(
                session_id=session_dict['session_id'],
                auth_token=session_dict['auth_token'],
                login_time=datetime.fromisoformat(session_dict['login_time']),
                operator_id=session_dict['operator_id'],
                ow_code=session_dict['ow_code'],
                expires_at=datetime.fromisoformat(session_dict['expires_at'])
            )
            
            # Sprawdź czy sesja nie wygasła
            if datetime.now() > self.session.expires_at:
                self.session = None
                return False
            
            return True
        except (KeyError, ValueError):
            return False
    def change_password(self, credentials: LoginCredentials, 
                       old_password: str, new_password: str) -> bool:
        """
        Zmienia hasło operatora
        
        Args:
            credentials: Dane logowania
            old_password: Stare hasło
            new_password: Nowe hasło
            
        Returns:
            True jeśli hasło zostało zmienione pomyślnie
        """
        if self.test_environment:
            # W środowisku testowym symulujemy zmianę hasła
            test_data = self.test_credentials.get(credentials.domain)
            if test_data and test_data["login"] == credentials.login and test_data["password"] == old_password:
                test_data["password"] = new_password
                return True
            else:
                raise AuthenticationException("Nieprawidłowe stare hasło")
        
        # Implementacja dla środowiska produkcyjnego
        raise NotImplementedError("Środowisko produkcyjne nie jest jeszcze zaimplementowane")
    
    def logout(self) -> bool:
        """
        Wylogowuje operatora z systemu
        
        Returns:
            True jeśli wylogowanie przebiegło pomyślnie
        """
        if not self.session:
            return True  # Już wylogowany
        
        try:
            if self.test_environment:
                # W środowisku testowym po prostu czyścimy sesję
                self.session = None
                return True
            
            # W środowisku produkcyjnym wyślij żądanie wylogowania
            xml_request = self._create_logout_xml()
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'logout'
            }
            
            response = requests.post(self.auth_url, data=xml_request, headers=headers)
            self.session = None
            
            return response.status_code == 200
            
        except Exception:
            # W przypadku błędu i tak czyścimy sesję lokalnie
            self.session = None
            return False
    
    def is_logged_in(self) -> bool:
        """
        Sprawdza czy operator jest zalogowany
        
        Returns:
            True jeśli jest aktywna sesja
        """
        if not self.session:
            return False
        
        # Sprawdzenie czy sesja nie wygasła
        if datetime.now() > self.session.expires_at:
            self.session = None
            return False
        
        return True
    
    def get_session_info(self) -> Optional[SessionInfo]:
        """
        Zwraca informacje o aktualnej sesji
        
        Returns:
            Informacje o sesji lub None jeśli nie ma aktywnej sesji
        """
        return self.session if self.is_logged_in() else None
    
    def get_test_pesels(self) -> Dict[str, str]:
        """
        Zwraca dostępne PESEL-e testowe
        
        Returns:
            Słownik z PESEL-ami testowymi
        """
        return self.test_pesels.copy()
    
    @staticmethod
    def _validate_pesel(pesel: str) -> bool:
        """
        Waliduje format numeru PESEL
        
        Args:
            pesel: Numer PESEL do walidacji
            
        Returns:
            True jeśli format jest poprawny
        """
        if not pesel or len(pesel) != 11:
            return False
        
        if not pesel.isdigit():
            return False
        
        # Sprawdzenie sumy kontrolnej PESEL
        weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
        checksum = sum(int(pesel[i]) * weights[i] for i in range(10)) % 10
        control_digit = (10 - checksum) % 10
        
        return int(pesel[10]) == control_digit
    
    @staticmethod
    def create_doctor_credentials(domain: str, login: str, password: str, 
                                doctor_id: str = None) -> LoginCredentials:
        """
        Tworzy dane logowania dla lekarza
        
        Args:
            domain: Kod OW NFZ
            login: Login lekarza
            password: Hasło
            doctor_id: ID lekarza (wymagane dla niektórych OW)
            
        Returns:
            Dane logowania lekarza
        """
        return LoginCredentials(
            domain=domain,
            login=login,
            password=password,
            operator_type=OperatorType.LEKARZ,
            doctor_id=doctor_id
        )
    
    @staticmethod
    def create_provider_credentials(domain: str, login: str, password: str, 
                                  provider_id: str = None) -> LoginCredentials:
        """
        Tworzy dane logowania dla świadczeniodawcy
        
        Args:
            domain: Kod OW NFZ
            login: Login świadczeniodawcy
            password: Hasło
            provider_id: ID świadczeniodawcy (wymagane dla niektórych OW)
            
        Returns:
            Dane logowania świadczeniodawcy
        """
        return LoginCredentials(
            domain=domain,
            login=login,
            password=password,
            operator_type=OperatorType.SWIADCZENIODAWCA,
            provider_id=provider_id
        )

# Przykład użycia
if __name__ == "__main__":
    # UWAGA: URL-e produkcyjne zostały poprawione na podstawie AuthService.php i BrokerService.php
    # Testowy:     https://ewus.nfz.gov.pl/ws-broker-server-ewus-auth-test
    # Produkcyjny: https://ewus.nfz.gov.pl/ws-broker-server-ewus (NIE auth-prod!)
    
    # Utworzenie klienta w środowisku testowym
    client = EWUSClient(test_environment=True)
    
    # Utworzenie danych logowania dla lekarza
    credentials = EWUSClient.create_doctor_credentials(
        domain="15",
        login="TEST1", 
        password="qwerty!@#"
    )
    
    try:
        # Logowanie
        session, status = client.login(credentials)
        print(f"Zalogowano pomyślnie: {session.operator_id}")
        print(f"Status logowania: {status}")
        
        # Sprawdzenie dostępnych PESEL-i testowych
        test_pesels = client.get_test_pesels()
        print(f"Dostępne PESEL-e testowe: {test_pesels}")
        
        # Sprawdzenie ubezpieczenia
        result = client.check_insurance(test_pesels["aktywny"])
        print(f"Status ubezpieczenia: {result.patient.insurance_status}")
        print(f"Pacjent: {result.patient.first_name} {result.patient.last_name}")
        print(f"Notatki: {result.notes}")
        
        # Sprawdzenie ubezpieczenia z dodatkowymi informacjami
        result = client.check_insurance(test_pesels["szczepienie"])
        print(f"Dodatkowe informacje: {result.patient.additional_info}")
        
        # Wylogowanie
        client.logout()
        print("Wylogowano pomyślnie")
        
    except EWUSException as e:
        print(f"Błąd eWUS: {e}")
    except Exception as e:
        print(f"Nieoczekiwany błąd: {e}")