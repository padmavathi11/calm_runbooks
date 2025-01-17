#script

import requests
from requests.auth import HTTPBasicAuth

PC_IP = "localhost"
pc_user = "@@{management_pc_username}@@".strip()
pc_password = "@@{management_pc_password}@@".strip()

def _build_url(scheme, resource_type, host=PC_IP, **params):
    _base_url = "/api/nutanix/v3"
    url = "{proto}://{host}".format(proto=scheme, host=host)
    port = params.get('nutanix_port', '9440')
    if port:
        url = url + ":{0}".format(port) + _base_url
    if resource_type.startswith("/"):
        url += resource_type
    else:
        url += "/{0}".format(resource_type)
    return url

def get_account_uuid():
    account = "@@{account_name}@@".strip()
    url = _build_url(scheme="https",resource_type="/accounts/list")
    data = requests.post(url, json={"kind":"account", "filter":"name==%s"%account},
                        auth=HTTPBasicAuth(pc_user, pc_password),
                        timeout=None, verify=False)       
    if account in str(data.json()):
        for new_data in data.json()['entities']:
           if new_data['metadata']['name'] == account: 
                account_uuid = new_data['metadata']['uuid']
                return account_uuid
    else:
        print("Error : %s account not present on %s"%(account,PC_IP))
        exit(1)    
            
def get_spec(**params):
    url = _build_url(scheme="https",
                    resource_type="/idempotence_identifiers")
    data = requests.post(url, json={"count": 1,"valid_duration_in_minutes": 527040},
                        auth=HTTPBasicAuth(pc_user, pc_password),
                        timeout=None, verify=False)                   
    if data.ok:
        _uuid = data.json()['uuid_list'][0]
    else:
        print("Error :- Failed to generate Idempotence UUID.")
        exit(1)
        
    #account_uuid = get_account_uuid()
    
    return (
    {"api_version": "3.1.0",
    "metadata": {
        "kind": "network_group_tunnel"
    },
    "spec": {
        "resources": {
            "platform_vpc_uuid_list": [
                params["vpc_uuid"]
            ],
            "tunnel_reference": {
                "kind": "tunnel",
                "uuid": _uuid,
                "name": params["tunnel_name"]
            },
            "account_reference": {
                "kind": "account",
                "uuid": params["account_uuid"]
            },
            "tunnel_vm_spec": {
                "vm_name": params["tunnel_name"]+"_"+params["vpc_name"]+"_TunnelVM",
                "subnet_uuid": params["overlay_subnet_uuid"],
                "cluster_uuid": params["cluster_uuid"]
            }
        },
        "name": params["tunnel_name"]
      }
    })

def create_tunnel(**params):
    payload = get_spec(**params)
    url = _build_url(scheme="https",
                    resource_type="network_groups/tunnels")
    data = requests.post(url, json=payload,
                        auth=HTTPBasicAuth(pc_user,pc_password),
                        timeout=None, verify=False)
    wait_for_completion(data)
    
def wait_for_completion(data):
    if data.ok:
        state = 'PENDING'
        while state == "PENDING":
            _uuid = data.json()["request_id"]
            url = _build_url(scheme="https",
                             resource_type="/tasks/%s"%_uuid)
            responce = requests.get(url, auth=HTTPBasicAuth(pc_user, pc_password),
                                    verify=False)                      
            if responce.json()['status'] in ['PENDING', 'RUNNING', 'QUEUED']:
                state = 'PENDING'
                sleep(5)                
            elif responce.json()['status'] == 'FAILED':
                print("Error occured ---> ",responce.json().get('message_list', 
                                            responce.json().get('error_detail', 
                                                                responce.json())))
                state = 'FAILED'
                exit(1)
            else:
                state = "SUCCEEDED"
    else:
        print("Error occured ---> ",data.json().get('message_list', 
                                data.json().get('error_detail', data.json())))
        exit(1)

vpc = @@{vpc_details}@@
#account = @@{account_details}@@
overlay_subnet = @@{overlay_subnet_details}@@
params = {"vpc_name" : vpc["name"],
          "vpc_uuid" : vpc["uuid"],
          "account_name" : "@@{account_name}@@".strip(),
          "account_uuid" : get_account_uuid(),
          "overlay_subnet_uuid" : overlay_subnet["uuid"],
          "cluster_uuid" : "@@{cluster_uuid}@@",
          "tunnel_name" : "@@{tenant_name}@@_VPC_Tunnel"
        }
create_tunnel(**params)
