import requests
import xml.etree.ElementTree as ET
import html
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
        
    def _parse_login_response(self, response_text: str) -> SessionInfo:
        """
        Parsuje odpowiedź SOAP z logowania
        
        Args:
            response_text: Odpowiedź SOAP z logowania
            
        Returns:
            Informacje o sesji
        """
        try:
            if self.debug:
                print("🔧 DEBUG - Parsowanie odpowiedzi logowania...")
                print(f"🔧 DEBUG - Długość odpowiedzi: {len(response_text)} znaków")
                
            root = ET.fromstring(response_text)
            
            if self.debug:
                print(f"🔧 DEBUG - Root element: {root.tag}")
                print(f"🔧 DEBUG - Root namespaces: {root.attrib}")
                
                # Wyświetl wszystkie elementy w odpowiedzi
                print("🔧 DEBUG - Wszystkie elementy w odpowiedzi:")
                for elem in root.iter():
                    print(f"  - {elem.tag}: {elem.text} | attrib: {elem.attrib}")
            
            # Sprawdź czy nie ma błędu SOAP fault
            fault = root.find(".//soapenv:Fault", {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/"})
            if fault is None:
                fault = root.find(".//soap:Fault", {"soap": "http://schemas.xmlsoap.org/soap/envelope/"})
            
            if fault is not None:
                if self.debug:
                    print("🔧 DEBUG - Znaleziono SOAP fault w odpowiedzi!")
                    fault_code = fault.find("faultcode")
                    fault_string = fault.find("faultstring") 
                    if fault_code is not None:
                        print(f"🔧 DEBUG - Fault code: {fault_code.text}")
                    if fault_string is not None:
                        print(f"🔧 DEBUG - Fault string: {fault_string.text}")
                self._parse_soap_fault(response_text)
            
            # Sprawdź błędy NFZ (com:faultcode)
            fault_code_nfz = root.find(".//com:faultcode", {"com": "http://xml.kamsoft.pl/ws/common"})
            if fault_code_nfz is not None:
                if self.debug:
                    print("🔧 DEBUG - Znaleziono NFZ fault code!")
                self._parse_soap_fault(response_text)
            
            # Szukaj session ID - używamy namespace który faktycznie jest w odpowiedzi
            session_elem = None
            
            # Spróbuj z namespace ns1 (jak w odpowiedzi)
            try:
                session_elem = root.find(".//ns1:session[@id]", {"ns1": "http://xml.kamsoft.pl/ws/common"})
                if session_elem is not None:
                    if self.debug:
                        print("🔧 DEBUG - Znaleziono session element z prefiksem ns1")
            except Exception as e:
                if self.debug:
                    print(f"🔧 DEBUG - Błąd z ns1: {e}")
            
            # Jeśli nie ma z ns1, spróbuj bez namespace (bezpośrednie wyszukiwanie)
            if session_elem is None:
                if self.debug:
                    print("🔧 DEBUG - Szukam session bez namespace...")
                for elem in root.iter():
                    if 'session' in elem.tag and 'id' in elem.attrib:
                        session_elem = elem
                        if self.debug:
                            print(f"🔧 DEBUG - Znaleziono session element: {elem.tag}")
                        break
            
            # Jeśli nie ma session w nagłówku, sprawdź w body
            if session_elem is None:
                if self.debug:
                    print("🔧 DEBUG - Nie znaleziono session w nagłówku, szukam w body...")
                
                # Sprawdź wszystkie elementy z atrybutem id
                for elem in root.iter():
                    if 'id' in elem.attrib and ('session' in elem.tag.lower() or len(elem.attrib.get('id', '')) > 10):
                        session_elem = elem
                        if self.debug:
                            print(f"🔧 DEBUG - Potencjalny session element: {elem.tag} = {elem.attrib}")
                        break
            
            if session_elem is None:
                if self.debug:
                    print("🔧 DEBUG - BŁĄD: Brak session ID w odpowiedzi!")
                    print("🔧 DEBUG - Wszystkie elementy z atrybutem 'id':")
                    for elem in root.iter():
                        if 'id' in elem.attrib:
                            print(f"  - {elem.tag}: id='{elem.attrib['id']}'")
                raise EWUSException("Brak session ID w odpowiedzi logowania")
            
            session_id = session_elem.get("id")
            if self.debug:
                print(f"🔧 DEBUG - Session ID: {session_id}")
            
            # Szukaj auth token - używamy ten sam sposób co dla session
            token_elem = None
            
            # Spróbuj z namespace ns1 (jak w odpowiedzi)
            try:
                token_elem = root.find(".//ns1:authToken[@id]", {"ns1": "http://xml.kamsoft.pl/ws/common"})
                if token_elem is not None:
                    if self.debug:
                        print("🔧 DEBUG - Znaleziono authToken element z prefiksem ns1")
            except Exception as e:
                if self.debug:
                    print(f"🔧 DEBUG - Błąd z ns1 dla token: {e}")
            
            # Jeśli nie ma z ns1, spróbuj bez namespace (bezpośrednie wyszukiwanie)
            if token_elem is None:
                if self.debug:
                    print("🔧 DEBUG - Szukam authToken bez namespace...")
                for elem in root.iter():
                    if ('token' in elem.tag.lower() or 'authtoken' in elem.tag.lower()) and 'id' in elem.attrib:
                        token_elem = elem
                        if self.debug:
                            print(f"🔧 DEBUG - Znaleziono token element: {elem.tag}")
                        break
            
            if token_elem is None:
                if self.debug:
                    print("🔧 DEBUG - BŁĄD: Brak auth token w odpowiedzi!")
                    print("🔧 DEBUG - Wszystkie elementy z 'token' lub 'auth' w nazwie:")
                    for elem in root.iter():
                        if 'token' in elem.tag.lower() or 'auth' in elem.tag.lower():
                            print(f"  - {elem.tag}: {elem.text} | attrib: {elem.attrib}")
                raise EWUSException("Brak auth token w odpowiedzi logowania")
            
            auth_token = token_elem.get("id")
            if self.debug:
                print(f"🔧 DEBUG - Auth Token: {auth_token}")
            
            # Szukaj informacji o operatorze
            operator_id = None
            
            # Sprawdź loginReturn dla dodatkowych informacji - używaj właściwy namespace
            login_return = None
            try:
                login_return = root.find(".//ns1:loginReturn", {"ns1": "http://xml.kamsoft.pl/ws/kaas/login_types"})
                if login_return is not None:
                    if self.debug:
                        print("🔧 DEBUG - Znaleziono loginReturn z ns1")
            except Exception as e:
                if self.debug:
                    print(f"🔧 DEBUG - Błąd z ns1 dla loginReturn: {e}")
            
            # Jeśli nie ma z ns1, spróbuj bezpośrednio
            if login_return is None:
                if self.debug:
                    print("🔧 DEBUG - Szukam loginReturn bez namespace...")
                for elem in root.iter():
                    if 'loginreturn' in elem.tag.lower():
                        login_return = elem
                        if self.debug:
                            print(f"🔧 DEBUG - Znaleziono loginReturn element: {elem.tag}")
                        break
            
            if login_return is not None and login_return.text:
                if self.debug:
                    print(f"🔧 DEBUG - LoginReturn message: {login_return.text}")
                
                # Próbuj wyciągnąć operator ID z komunikatu
                message = login_return.text
                if self.debug:
                    print(f"🔧 DEBUG - LoginReturn message (raw): {message}")
                    # Dekoduj HTML entities dla czytelności
                    try:
                        import html
                        decoded_message = html.unescape(message)
                        print(f"🔧 DEBUG - LoginReturn message (decoded): {decoded_message}")
                    except:
                        decoded_message = message
                # Szukaj wzorców jak "ID operatora: 12345" itp.
                import re
                patterns = [
                    r'operatora?\s*:?\s*(\w+)',
                    r'operator\s*ID\s*:?\s*(\w+)',
                    r'ID\s*:?\s*(\w+)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        operator_id = match.group(1)
                        if self.debug:
                            print(f"🔧 DEBUG - Operator ID z komunikatu: {operator_id}")
                        break
            
            # Jeśli nie znaleziono operator ID, utwórz na podstawie session
            if not operator_id:
                operator_id = f"OP_{session_id[:8]}"
                if self.debug:
                    print(f"🔧 DEBUG - Wygenerowany Operator ID: {operator_id}")
            
            # Domyślny OW code (zostanie nadpisany w login())
            ow_code = "00"
            
            session_info = SessionInfo(
                session_id=session_id,
                auth_token=auth_token,
                login_time=datetime.now(),
                operator_id=operator_id,
                ow_code=ow_code,
                expires_at=datetime.now() + timedelta(hours=8)
            )
            
            if self.debug:
                print("🔧 DEBUG - SessionInfo utworzony pomyślnie!")
                print(f"🔧 DEBUG - Session ID: {session_info.session_id}")
                print(f"🔧 DEBUG - Auth Token: {session_info.auth_token}")
                print(f"🔧 DEBUG - Operator ID: {session_info.operator_id}")
                print(f"🔧 DEBUG - Expires at: {session_info.expires_at}")
                
            return session_info
            
        except ET.ParseError as e:
            error_msg = f"Nie można sparsować odpowiedzi logowania XML: {str(e)}"
            if self.debug:
                print(f"🔧 DEBUG - BŁĄD XML Parse: {error_msg}")
                print(f"🔧 DEBUG - Problematyczny XML (pierwsze 500 znaków):")
                print(response_text[:500])
            raise EWUSException(error_msg)
            
        except Exception as e:
            error_msg = f"Błąd podczas parsowania logowania: {str(e)}"
            if self.debug:
                print(f"🔧 DEBUG - BŁĄD parsowania: {error_msg}")
                import traceback
                traceback.print_exc()
            raise EWUSException(error_msg)
    
    def _determine_login_status(self, response_text: str) -> LoginStatus:
        """
        Określa status logowania na podstawie odpowiedzi
        
        Args:
            response_text: Odpowiedź SOAP z logowania
            
        Returns:
            Status logowania
        """
        try:
            root = ET.fromstring(response_text)
            
            # Znajdź komunikat loginReturn - używaj bezpieczne wyszukiwanie
            login_return = None
            
            # Spróbuj z namespace ns1
            try:
                login_return = root.find(".//ns1:loginReturn", {"ns1": "http://xml.kamsoft.pl/ws/kaas/login_types"})
                if login_return is not None:
                    if self.debug:
                        print("🔧 DEBUG - Znaleziono loginReturn dla statusu z ns1")
            except Exception as e:
                if self.debug:
                    print(f"🔧 DEBUG - Błąd z ns1 dla status loginReturn: {e}")
            
            # Jeśli nie ma z ns1, spróbuj bezpośrednio
            if login_return is None:
                if self.debug:
                    print("🔧 DEBUG - Szukam loginReturn dla statusu bez namespace...")
                for elem in root.iter():
                    if 'loginreturn' in elem.tag.lower():
                        login_return = elem
                        if self.debug:
                            print(f"🔧 DEBUG - Znaleziono loginReturn dla statusu: {elem.tag}")
                        break
            
            if login_return is not None and login_return.text:
                message = login_return.text
                if self.debug:
                    print(f"🔧 DEBUG - Sprawdzam status z komunikatu: {message}")
                
                # Dekoduj HTML entities
                try:
                    import html
                    message = html.unescape(message)
                    if self.debug:
                        print(f"🔧 DEBUG - Dekodowany komunikat: {message}")
                except:
                    pass
                
                # Sprawdź kody statusu zgodnie z dokumentacją NFZ
                if "[000]" in message:
                    if self.debug:
                        print("🔧 DEBUG - Status: SUCCESS [000]")
                    return LoginStatus.SUCCESS
                elif "[001]" in message:
                    if self.debug:
                        print("🔧 DEBUG - Status: PASSWORD_EXPIRES_SOON [001]")
                    return LoginStatus.PASSWORD_EXPIRES_SOON
                elif "[002]" in message:
                    if self.debug:
                        print("🔧 DEBUG - Status: PASSWORD_EXPIRES_TOMORROW [002]")
                    return LoginStatus.PASSWORD_EXPIRES_TOMORROW
                elif "[003]" in message:
                    if self.debug:
                        print("🔧 DEBUG - Status: PASSWORD_EXPIRES_TODAY [003]")
                    return LoginStatus.PASSWORD_EXPIRES_TODAY
            
            # Domyślnie sukces jeśli nie ma komunikatu o wygaśnięciu hasła
            if self.debug:
                print("🔧 DEBUG - Status: domyślny SUCCESS")
            return LoginStatus.SUCCESS
            
        except ET.ParseError as e:
            if self.debug:
                print(f"🔧 DEBUG - Błąd parsowania dla statusu: {e}")
            return LoginStatus.SUCCESS
    
    def _parse_check_cwu_response(self, response_text: str, pesel: str) -> InsuranceCheckResult:
        """
        Parsuje odpowiedź SOAP z sprawdzania ubezpieczenia
        
        Args:
            response_text: Odpowiedź SOAP z sprawdzania ubezpieczenia
            pesel: PESEL pacjenta (dla kontekstu)
            
        Returns:
            Wynik sprawdzenia ubezpieczenia
        """
        try:
            root = ET.fromstring(response_text)
            
            # Sprawdź czy nie ma błędu
            if root.find(".//soapenv:Fault", {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/"}) is not None:
                self._parse_soap_fault(response_text)
            
            # Znajdź główny element odpowiedzi
            response_elem = root.find(".//ewus:status_cwu_odp", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            if response_elem is None:
                raise EWUSException("Brak elementu status_cwu_odp w odpowiedzi")
            
            # Podstawowe informacje o operacji
            operation_id = response_elem.get("id_operacji", str(uuid.uuid4()).replace("-", "")[:20])
            operation_date_str = response_elem.get("data_czas_operacji")
            
            try:
                operation_date = datetime.fromisoformat(operation_date_str.replace(" ", "T")) if operation_date_str else datetime.now()
            except:
                operation_date = datetime.now()
            
            # Informacje o systemie NFZ
            system_nfz = root.find(".//ewus:system_nfz", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            
            # Status CWU
            status_cwu_elem = root.find(".//ewus:status_cwu", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            status_cwu = int(status_cwu_elem.text) if status_cwu_elem is not None and status_cwu_elem.text else 0
            
            # Dane operatora
            operator_elem = root.find(".//ewus:id_operatora", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            operator_id = operator_elem.text if operator_elem is not None else self.session.operator_id
            
            ow_elem = root.find(".//ewus:id_ow", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            ow_code = ow_elem.text if ow_elem is not None else self.session.ow_code
            
            provider_elem = root.find(".//ewus:id_swiad", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            provider_id = provider_elem.text if provider_elem is not None else None
            
            # Status ubezpieczenia
            status_ubezp_elem = root.find(".//ewus:status_ubezp", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            insurance_status_val = 0
            status_symbol = None
            
            if status_ubezp_elem is not None:
                insurance_status_val = int(status_ubezp_elem.text) if status_ubezp_elem.text else 0
                status_symbol = status_ubezp_elem.get("ozn_rec")
            
            # Mapowanie statusu ubezpieczenia
            if status_cwu == 1:
                if insurance_status_val == 1:
                    insurance_status = InsuranceStatus.AKTYWNY
                    is_valid = True
                    notes = ["Pacjent ma aktywne ubezpieczenie"]
                else:
                    insurance_status = InsuranceStatus.NIEAKTYWNY
                    is_valid = False
                    notes = ["Brak aktywnego ubezpieczenia"]
            elif status_cwu == -1:
                insurance_status = InsuranceStatus.PESEL_NIEAKTUALNY
                is_valid = False
                notes = ["PESEL nieaktualny - anulowany przez MSW"]
            else:
                insurance_status = InsuranceStatus.NIEAKTYWNY
                is_valid = False
                notes = ["Brak pozycji w systemie CWU"]
            
            # Dane pacjenta
            pesel_elem = root.find(".//ewus:numer_pesel", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            pesel_response = pesel_elem.text if pesel_elem is not None else pesel
            
            first_name_elem = root.find(".//ewus:imie", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            first_name = first_name_elem.text if first_name_elem is not None else None
            
            last_name_elem = root.find(".//ewus:nazwisko", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            last_name = last_name_elem.text if last_name_elem is not None else None
            
            # Data ważności potwierdzenia
            expiration_elem = root.find(".//ewus:data_waznosci_potwierdzenia", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            expiration_date = None
            if expiration_elem is not None and expiration_elem.text:
                try:
                    expiration_date = datetime.fromisoformat(expiration_elem.text.replace(" ", "T"))
                except:
                    pass
            
            # Informacje dodatkowe
            additional_info = []
            info_dodatkowe = root.find(".//ewus:informacje_dodatkowe", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"})
            if info_dodatkowe is not None:
                for info in info_dodatkowe.findall(".//ewus:informacja", {"ewus": "https://ewus.nfz.gov.pl/ws/broker/ewus/status_cwu/v5"}):
                    kod = info.get("kod", "")
                    poziom = info.get("poziom", "")
                    wartosc = info.get("wartosc", "")
                    
                    additional_info.append({
                        "kod": kod,
                        "poziom": poziom,
                        "wartosc": wartosc
                    })
                    
                    # Dodaj informacje o specjalnych statusach do notatek
                    if "COVID" in kod.upper():
                        if "ZASWIADCZENIE" in kod.upper():
                            notes.append("Posiada zaświadczenie o szczepieniu COVID-19")
                        elif "KWARANTANNA" in kod.upper():
                            notes.append("Objęty kwarantanną COVID-19")
                        elif "IZOLACJA" in kod.upper():
                            notes.append("W izolacji domowej COVID-19")
                    elif "UKR" in kod.upper():
                        notes.append("Uprawnienia dla obywateli Ukrainy")
            
            # Utworzenie obiektu PatientInfo
            patient = PatientInfo(
                pesel=pesel_response,
                first_name=first_name,
                last_name=last_name,
                insurance_status=insurance_status,
                status_symbol=status_symbol,
                expiration_date=expiration_date,
                additional_info=additional_info if additional_info else None
            )
            
            return InsuranceCheckResult(
                operation_id=operation_id,
                operation_date=operation_date,
                patient=patient,
                operator_id=operator_id,
                ow_code=ow_code,
                provider_id=provider_id,
                is_valid=is_valid,
                notes=notes
            )
            
        except ET.ParseError as e:
            raise EWUSException(f"Nie można sparsować odpowiedzi sprawdzania ubezpieczenia: {str(e)}")
        except Exception as e:
            raise EWUSException(f"Błąd podczas parsowania odpowiedzi: {str(e)}")
    
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
            # Utworzenie XML żądania
            xml_request = self._create_login_xml(credentials)
            
            if self.debug:
                print("🔧 DEBUG - Wysyłany XML:")
                print(xml_request)
                print("🔧 DEBUG - URL:", self.auth_url)
                print("🔧 DEBUG - Środowisko testowe:", self.test_environment)
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://xml.kamsoft.pl/ws/auth/Auth/loginRequest'
            }
            
            if self.debug:
                print("🔧 DEBUG - Nagłówki:", headers)
            
            # Wysłanie żądania SOAP
            response = requests.post(self.auth_url, data=xml_request, headers=headers, timeout=30)
            
            if self.debug:
                print("🔧 DEBUG - Status kod odpowiedzi:", response.status_code)
                print("🔧 DEBUG - Nagłówki odpowiedzi:", dict(response.headers))
                print("🔧 DEBUG - Pełna odpowiedź XML:")
                print("=" * 80)
                print(response.text)
                print("=" * 80)
            
            # Sprawdzenie statusu HTTP
            if response.status_code != 200:
                if self.debug:
                    print(f"🔧 DEBUG - BŁĄD HTTP: Status {response.status_code}")
                    print(f"🔧 DEBUG - Treść błędu: {response.text[:500]}...")
                
                # Sprawdź czy to błąd SOAP czy HTTP
                if response.status_code == 500:
                    # Błąd 500 może zawierać SOAP fault
                    if self.debug:
                        print("🔧 DEBUG - Próba parsowania SOAP fault z błędu 500...")
                    self._parse_soap_fault(response.text)
                else:
                    raise EWUSException(f"Błąd HTTP {response.status_code}: {response.text[:300]}...")
            
            # Sprawdzenie czy odpowiedź zawiera XML
            if not response.text.strip():
                raise EWUSException("Pusta odpowiedź serwera")
            
            if not response.text.strip().startswith('<?xml') and not response.text.strip().startswith('<'):
                if self.debug:
                    print("🔧 DEBUG - BŁĄD: Odpowiedź nie jest XML-em!")
                    print(f"🔧 DEBUG - Pierwsze 200 znaków: {response.text[:200]}")
                raise EWUSException(f"Odpowiedź nie jest w formacie XML: {response.text[:200]}...")
            
            # Parsowanie odpowiedzi logowania
            if self.debug:
                print("🔧 DEBUG - Rozpoczynam parsowanie odpowiedzi logowania...")
            
            session_info = self._parse_login_response(response.text)
            session_info.ow_code = credentials.domain  # Ustawiamy prawdziwy kod OW
            
            # Określenie statusu logowania
            if self.debug:
                print("🔧 DEBUG - Określam status logowania...")
            
            login_status = self._determine_login_status(response.text)
            
            if self.debug:
                print(f"🔧 DEBUG - Status logowania: {login_status}")
                print(f"🔧 DEBUG - Session ID: {session_info.session_id}")
                print(f"🔧 DEBUG - Auth Token: {session_info.auth_token}")
                print(f"🔧 DEBUG - Operator ID: {session_info.operator_id}")
                print(f"🔧 DEBUG - OW Code: {session_info.ow_code}")
            
            # Zapisanie sesji
            self.session = session_info
            
            if self.debug:
                print("🔧 DEBUG - Logowanie zakończone pomyślnie!")
            
            return session_info, login_status
            
        except requests.exceptions.Timeout:
            error_msg = "Timeout połączenia z serwerem eWUS"
            if self.debug:
                print(f"🔧 DEBUG - BŁĄD: {error_msg}")
            raise EWUSException(error_msg)
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Błąd połączenia z serwerem eWUS: {str(e)}"
            if self.debug:
                print(f"🔧 DEBUG - BŁĄD POŁĄCZENIA: {error_msg}")
            raise EWUSException(error_msg)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Błąd HTTP podczas logowania: {str(e)}"
            if self.debug:
                print(f"🔧 DEBUG - BŁĄD HTTP: {error_msg}")
            raise EWUSException(error_msg)
            
        except Exception as e:
            if isinstance(e, EWUSException):
                if self.debug:
                    print(f"🔧 DEBUG - Przekazuję wyjątek eWUS: {str(e)}")
                raise
            
            error_msg = f"Nieoczekiwany błąd podczas logowania: {str(e)}"
            if self.debug:
                print(f"🔧 DEBUG - NIEOCZEKIWANY BŁĄD: {error_msg}")
                import traceback
                print("🔧 DEBUG - Stack trace:")
                traceback.print_exc()
            raise EWUSException(error_msg)
    
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
            
            if self.debug:
                print("🔧 DEBUG - Wysyłany XML (check insurance):")
                print(xml_request)
                print("🔧 DEBUG - URL:", self.broker_url)
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'executeService'
            }
            
            if self.debug:
                print("🔧 DEBUG - Nagłówki (check insurance):", headers)
            
            response = requests.post(self.broker_url, data=xml_request, headers=headers)
            
            if self.debug:
                print("🔧 DEBUG - Status kod (check insurance):", response.status_code)
                print("🔧 DEBUG - Odpowiedź (check insurance):")
                print(response.text)
            
            if response.status_code != 200:
                if response.status_code == 500:
                    self._parse_soap_fault(response.text)
                else:
                    raise EWUSException(f"Błąd HTTP {response.status_code}: {response.text[:300]}...")
            
            # Parsowanie odpowiedzi z sprawdzania ubezpieczenia
            result = self._parse_check_cwu_response(response.text, pesel)
            return result
            
        except Exception as e:
            if isinstance(e, EWUSException):
                raise
            raise EWUSException(f"Błąd podczas sprawdzania ubezpieczenia: {str(e)}")
    
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
        try:
            xml_request = self._create_change_password_xml(credentials, old_password, new_password)
            
            if self.debug:
                print("🔧 DEBUG - Wysyłany XML (change password):")
                print(xml_request)
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'changePassword'
            }
            
            response = requests.post(self.auth_url, data=xml_request, headers=headers)
            
            if self.debug:
                print("🔧 DEBUG - Status kod (change password):", response.status_code)
                print("🔧 DEBUG - Odpowiedź (change password):")
                print(response.text)
            
            if response.status_code != 200:
                if response.status_code == 500:
                    self._parse_soap_fault(response.text)
                else:
                    raise EWUSException(f"Błąd HTTP {response.status_code}: {response.text[:300]}...")
            
            # Sprawdź czy w odpowiedzi nie ma błędu
            try:
                root = ET.fromstring(response.text)
                if root.find(".//soapenv:Fault", {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/"}) is not None:
                    self._parse_soap_fault(response.text)
            except ET.ParseError:
                pass
            
            # Jeśli dotarliśmy tutaj, zmiana hasła przebiegła pomyślnie
            return True
            
        except Exception as e:
            if isinstance(e, EWUSException):
                raise
            raise EWUSException(f"Błąd podczas zmiany hasła: {str(e)}")
    
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
            
            if self.debug:
                print("🔧 DEBUG - Wysyłany XML (logout):")
                print(xml_request)
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'logout'
            }
            
            response = requests.post(self.auth_url, data=xml_request, headers=headers)
            
            if self.debug:
                print("🔧 DEBUG - Status kod (logout):", response.status_code)
                print("🔧 DEBUG - Odpowiedź (logout):")
                print(response.text)
            
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
    # System obsługuje pełne środowiska testowe i produkcyjne NFZ
    # Testowy:     https://ewus.nfz.gov.pl/ws-broker-server-ewus-auth-test
    # Produkcyjny: https://ewus.nfz.gov.pl/ws-broker-server-ewus
    
    # Utworzenie klienta w środowisku testowym
    client = EWUSClient(test_environment=True, debug=False)
    
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