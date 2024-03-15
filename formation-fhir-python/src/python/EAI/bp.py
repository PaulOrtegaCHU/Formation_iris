from grongier.pex import BusinessProcess
import iris
import jwt
import json
from fhir.resources import patient, bundle
from fhir.resources.patient import Patient
from fhir.resources.bundle import Bundle
from msg import FilterPatientResource

class FilterPatientProcess(BusinessProcess):

    def filter_patient_resource(self, request:FilterPatientResource) -> FilterPatientResource:
        """
        This function will filter the patient resource.

        It will remove the name, address, telecom and birthdate fields from the patient resource.

        The function will return the filtered patient resource as a string.

        We will use the fhir.resources library to parse the patient resource.

        Notice the signature of the function.

        The function takes a string as input and returns a string as output.

        So we need to parse the input string to a fhir.resources.patient.Patient object and then parse the fhir.resources.patient.Patient object to a string.
        """
        # parse the patient resource
        p = patient.Patient.parse_obj(json.loads(request.patient_str))
        # remove the fields
        p.name = []
        p.address = []
        p.telecom = []
        p.birthDate = None
        p.gender = None
        # return the filtered patient resource as a string
        return FilterPatientResource(p.json())


class MyBusinessProcess(BusinessProcess):

    def on_init(self):
        if not hasattr(self, 'target'):
            self.target = 'HS.FHIRServer.Interop.HTTPOperation'
            return

    def on_fhir_request(self, request: 'iris.HS.FHIRServer.Interop.Request'):
        # Do something with the request
        self.log_info('Received a FHIR request 2')

        # pass it to the target
        rsp = self.send_request_sync(self.target, request)

        # Try to get the token from the request
        token = request.Request.AdditionalInfo.GetAt("USER:OAuthToken") or ""

        decoded_token = jwt.decode(token, options={"verify_signature": False})
        self.log_info(f'Token scope : {decoded_token["scope"]}')
        
        # Do something with the response
        if self.check_token(token):
            self.log_info('Filtering the response')
            # Filter the response
            payload_str = self.quick_stream_to_string(rsp.QuickStreamId)

            # if the payload is empty, return the response
            if payload_str == '':
                return rsp

            filtered_payload_string = self.filter_resources(payload_str)

            # write the json string to a quick stream
            quick_stream = self.string_to_quick_stream(filtered_payload_string)

            # return the response
            rsp.QuickStreamId = quick_stream._Id()

        return rsp

    
    def check_token(self, token: str) -> bool:
        try:
            # Décoder le token JWT sans vérification de la signature (puisque nous n'avons pas de clé secrète)
            decoded_token = jwt.decode(token, options={"verify_signature": False})

            # Vérifier si le champ "scope" existe et s'il est égal à "VIP"
            if "scope" in decoded_token and "superRead" in decoded_token["scope"]:
                return False
            else:
                return True
        except jwt.ExpiredSignatureError:
            # Le jeton a expiré
            return False
        except jwt.DecodeError:
            # Erreur lors du décodage du jeton
            return False


    def filter_resources(self, resource_str:str) -> str:
        """
        This function will filter the resources.

        We need to check the resource type and filter the resource based on the resource type.

        If the resource type is Bundle, we need to filter all the entries of the bundle that are of type Patient.

        If the resource type is Patient, we need to filter the patient resource.

        The function will return the filtered resource as a string.

        We will use the fhir.resources library to parse the resource.
        """
        # parse the resource
        r = json.loads(resource_str)

        if 'resourceType' not in r:
            return resource_str

        if r['resourceType'] == 'Bundle':
            # parse the bundle
            b = bundle.Bundle.parse_obj(r)
            # filter the entries
            for entry in b.entry:
                #vérifier cas où bundle vide, source erreur
                if hasattr(entry, 'resource') and entry.resource.resource_type == 'Patient' :
                    entry.resource = patient.Patient.parse_obj(json.loads(self.send_request_sync("Python.EAI.bp.FilterPatientProcess",FilterPatientResource(entry.resource.json())).patient_str))
            # return the filtered bundle as a string
            return b.json()
        elif r['resourceType'] == 'Patient':
            # filter the patient resource
            return self.send_request_sync("Python.EAI.bp.FilterPatientProcess",FilterPatientResource((json.dumps(r)))).patient_str
        else:
            return resource_str


    def quick_stream_to_string(self, quick_stream_id) -> str:
        quick_stream = iris.cls('HS.SDA3.QuickStream')._OpenId(quick_stream_id)
        json_payload = ''
        while quick_stream.AtEnd == 0:
            json_payload += quick_stream.Read()

        return json_payload
    
    def string_to_quick_stream(self, json_string:str):
        quick_stream = iris.cls('HS.SDA3.QuickStream')._New()

        # write the json string to the payload
        n = 3000
        chunks = [json_string[i:i+n] for i in range(0, len(json_string), n)]
        for chunk in chunks:
            quick_stream.Write(chunk)

        return quick_stream