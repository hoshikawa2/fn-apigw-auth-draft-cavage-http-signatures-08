from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64
import json
from datetime import datetime
import io
from fdk import response
import oci
import requests

def get_date():
    d = str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'))
    return d

def get_signing(d, streaming_host, oci_region):
    with open('oci_api_key.pem', 'rb') as key_file:
        private_key = load_pem_private_key(key_file.read(), password=None)# Dados para assinar
    str = b'(request-target): post /20180418/streams/<streaming_host>/groupCursors\ndate: <date_str>\nhost: cell-1.streaming.<oci_region>.oci.oraclecloud.com'# Assine os dados usando SHA-256 e a chave privada

    data = str.replace(b'<date_str>', bytes(d.encode())).replace(b'<streaming_host>', bytes(streaming_host.encode())).replace(b'<oci_region>', bytes(oci_region.encode()))
    signature = private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())# Imprima a assinatura

    base64_encoded = base64.b64encode(signature)

    return base64_encoded

def get_authorization(d, streaming_host, oci_region, tenancy, user, fingerprint):
    a = get_signing(d, streaming_host, oci_region)
    s = b'Signature algorithm="rsa-sha256",headers="(request-target) date host",keyId="<tenancy>/<user>/<fingerprint>",signature="<signature>",version="1"'
    s = s.replace(b'<signature>', a).replace(b'<tenancy>', bytes(tenancy.encode())).replace(b'<user>', bytes(user.encode())).replace(b'<fingerprint>', bytes(fingerprint.encode()))
    r = s.decode()
    return r

def auth_idcs(token, url, clientID, secretID):
    url = url + "/oauth2/v1/introspect"

    auth = clientID + ":" + secretID
    auth_bytes = auth.encode("ascii")
    auth_base64_bytes = base64.b64encode(auth_bytes)
    auth_base64_message = auth_base64_bytes.decode("ascii")

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + auth_base64_message
    }

    payload = "token=" + token

    response = requests.request("POST", url, headers=headers, data=payload)
    return response

#Function used to load the configurations from the config.json file
def getOptions():
    fo = open("config.json", "r")
    config = fo.read()
    options = json.loads(config)
    return options

def handler(ctx, data: io.BytesIO = None):
    config = oci.config.from_file("config")
    logging = oci.loggingingestion.LoggingClient(config)
    tenancy = config['tenancy']
    user = config['user']
    fingerprint = config['fingerprint']

    app_context = dict(ctx.Config())
    streaming_host = app_context['streaming_host']
    oci_region = app_context['oci_region']
    jsonData = ""

    options = getOptions()

    try:
        header = json.loads(data.getvalue().decode('utf-8'))["data"]
        access_token = header["token"]
        url = options["BaseUrl"]

        authorization = auth_idcs(access_token, url, options["ClientId"], options["ClientSecret"])
        if authorization.json().get("active") == False:
            return response.Response(
                ctx,
                status_code=401,
                response_data=json.dumps({"active": False, "wwwAuthenticate": jsonData})
            )

        d = get_date()
        a = get_authorization(d, streaming_host=streaming_host, oci_region=oci_region, tenancy=tenancy, user=user, fingerprint=fingerprint)

        rdata = json.dumps({
                "active": True,
                "context": {
                    "date": d,
                    "authorization": a,
                    "streaming_host": streaming_host,
                    "oci_region": oci_region,
                    "tenancy": tenancy,
                    "user": user,
                    "fingerprint": fingerprint
                }})

        put_logs_response = logging.put_logs(
            log_id="ocid1.log.oc1.iad.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            put_logs_details=oci.loggingingestion.models.PutLogsDetails(
                specversion="EXAMPLE-specversion-Value",
                log_entry_batches=[
                    oci.loggingingestion.models.LogEntryBatch(
                        entries=[
                            oci.loggingingestion.models.LogEntry(
                                data="authorization: " + str(a),
                                id="ocid1.test.oc1..00000001.EXAMPLE-id-Value")],
                        source="EXAMPLE-source-Value",
                        type="EXAMPLE-type-Value")]))

        put_logs_response = logging.put_logs(
            log_id="ocid1.log.oc1.iad.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            put_logs_details=oci.loggingingestion.models.PutLogsDetails(
                specversion="EXAMPLE-specversion-Value",
                log_entry_batches=[
                    oci.loggingingestion.models.LogEntryBatch(
                        entries=[
                            oci.loggingingestion.models.LogEntry(
                                data="request payload: " + json.dumps(header),
                                id="ocid1.test.oc1..00000001.EXAMPLE-id-Value-1")],
                        source="EXAMPLE-source-Value",
                        type="EXAMPLE-type-Value")]))

        put_logs_response = logging.put_logs(
            log_id="ocid1.log.oc1.iad.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            put_logs_details=oci.loggingingestion.models.PutLogsDetails(
                specversion="EXAMPLE-specversion-Value",
                log_entry_batches=[
                    oci.loggingingestion.models.LogEntryBatch(
                        entries=[
                            oci.loggingingestion.models.LogEntry(
                                data="access: " + json.dumps(authorization.text),
                                id="ocid1.test.oc1..00000001.EXAMPLE-id-Value-1")],
                        source="EXAMPLE-source-Value",
                        type="EXAMPLE-type-Value")]))


        return response.Response(
                ctx, response_data=rdata,
                status_code=200,
                headers={"Content-Type": "application/json", "Authorization": a, "Date": d}
        )

    except(Exception) as ex:
        jsonData = 'error parsing json payload: ' + str(ex)
        put_logs_response = logging.put_logs(
            log_id="ocid1.log.oc1.iad.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            put_logs_details=oci.loggingingestion.models.PutLogsDetails(
                specversion="EXAMPLE-specversion-Value",
                log_entry_batches=[
                    oci.loggingingestion.models.LogEntryBatch(
                        entries=[
                            oci.loggingingestion.models.LogEntry(
                                data="error: " + jsonData,
                                id="ocid1.test.oc1..00000001.EXAMPLE-id-Value")],
                        source="EXAMPLE-source-Value",
                        type="EXAMPLE-type-Value")]))

        pass

    return response.Response(
        ctx,
        status_code=401,
        response_data=json.dumps({"active": False, "wwwAuthenticate": jsonData})
    )