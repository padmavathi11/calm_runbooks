# script

import requests
from requests.auth import HTTPBasicAuth

PC_IP = "@@{PC_IP}@@".strip()
pc_username = "@@{prism_central_username}@@".strip()
pc_password = "@@{prism_central_passwd}@@".strip()
skip_delete = False

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

def _get_cluster_details(cluster_name):
    payload = {"kind": "cluster"}
    url = _build_url(scheme="https",
                    resource_type="/clusters/list")
    data = requests.post(url, json=payload,
                         auth=HTTPBasicAuth(pc_username, pc_password), 
                         verify=False)
    if data.ok:
        for _cluster in data.json()['entities']:
            if _cluster['status']['name'] == cluster_name:
                print("cluster_uuid={}".format(_cluster['metadata']['uuid']))
                return str(_cluster['metadata']['uuid'])
        print("Input Error :- Given cluster %s not present on %s"%(cluster_name, PC_IP))
        exit(1)
    else:
        print("Error while fetching %s cluster info"%cluster_name)
        print(data.json().get('message_list',data.json().get('error_detail', data.json())))
        exit(1)
            
def _get_virtual_switch_uuid(virtual_switch_name, cluster_uuid): 
    payload = {"entity_type": "distributed_virtual_switch", 
               "filter": "name==%s"%virtual_switch_name}
    url = _build_url(scheme="https",
                    resource_type="/groups")                
    data = requests.post(url, json=payload,
                         auth=HTTPBasicAuth(pc_username, pc_password),
                         verify=False)
    if data.ok:
        _uuid = data.json()['group_results'][0]['entity_results'][0]['entity_id']
        _url = "https://%s:9440/api/networking/v2.a1/dvs/virtual-switches/%s?proxyClusterUuid=%s"%(PC_IP,
                                                                                                _uuid,
                                                                                                cluster_uuid)
        _data = requests.get(_url, auth=HTTPBasicAuth(pc_username, pc_password),verify=False)
        if _data.json()['data']['name'] == virtual_switch_name:
            print("virtual switch uuid ----> ",_uuid)
            return str(_uuid)
        else:
            print("Input Error :- %s virtual switch not present on %s"%(virtual_switch_name, PC_IP))
            exit(1)
    else:
        print("Error while fetching virtual switch details :- ",data.json().get('message_list',
                                                                                data.json().get('error_detail', 
                                                                                data.json())))

def _get_subnet_uuid(subnet, delete=False):
    global skip_delete
    url = _build_url(scheme="https",resource_type="/subnets/list")
    data = requests.post(url, json={"kind":"subnet", "filter":"name==%s"%subnet},
                         auth=HTTPBasicAuth(pc_username, 
                                            pc_password),
                         timeout=None, verify=False)
    if data.ok:
        if data.json()['metadata']['total_matches'] == 0:
            print("%s not present on %s"%(subnet, PC_IP))
            skip_delete = True
            if not delete:
                exit(1)
        elif data.json()['metadata']['total_matches'] > 1:
            print("There are more than one subnets with name - %s on - %s"%(subnet, PC_IP))
            print("Please delete it manually before executing runbook.")
            exit(1)
        else:
            skip_delete = False
            return data.json()['entities'][0]['metadata']['uuid']
    else:
        print("Error while fetching subnet details :- ",data.json().get('message_list',
                                     data.json().get('error_detail', data.json())))
        exit(1)
        
def get_subnet_details(_uuid):
    url = _build_url(scheme="https",resource_type="/subnets/%s"%_uuid)
    data = requests.get(url, auth=HTTPBasicAuth(pc_username, pc_password),
                        timeout=None, verify=False)
    if not data.ok:
        print("Error while fetching project subnet details.")
        print(data.json().get('message_list',\
            data.json().get('error_detail', data.json())))
        exit(1)
    else:
        print("project_subnet_address={}".format(data.json()['spec']\
            ['resources']['ip_config']['pool_list'][0]['range'].split( )[-1]))
        
def _get_vpc_uuid(vpc_name):
    global skip_delete
    url = _build_url(scheme="https",resource_type="/vpcs/list")
    data = requests.post(url, json={"kind":"vpc", "filter":"name==%s"%vpc_name},
                         auth=HTTPBasicAuth(pc_username, 
                                            pc_password),
                         timeout=None, verify=False)
    if data.ok:
        if data.json()['metadata']['total_matches'] == 0:
            print("%s not present on %s"%(vpc_name, PC_IP))
            skip_delete = True
        elif data.json()['metadata']['total_matches'] > 1:
            print("There are more than one VPC's with name - %s on - %s"%(vpc_name, PC_IP))
            print("Please delete it manually before executing runbook.")
            exit(1)
        else:
            skip_delete = False
            return data.json()['entities'][0]['metadata']['uuid']
    else:
        print("Error while fetching VPC details :- ",data.json().get('message_list',
                                     data.json().get('error_detail', data.json())))
        exit(1)
        
def _get_project_uuid(project_name):
    global skip_delete
    url = _build_url(scheme="https",resource_type="/projects/list")
    data = requests.post(url, json={"kind":"project", "filter":"name==%s"%project_name},
                         auth=HTTPBasicAuth(pc_username, 
                                            pc_password),
                         timeout=None, verify=False)
    if data.ok:
        if data.json()['metadata']['total_matches'] == 0:
            print("%s not present on %s"%(project_name, PC_IP))
            skip_delete = True
        elif data.json()['metadata']['total_matches'] > 1:
            print("There are more than one projects with name - %s on - %s"%(project_name, PC_IP))
            print("Please delete it manually before executing runbook.")
            exit(1)
        else:
            skip_delete = False
            return data.json()['entities'][0]['metadata']['uuid']
    else:
        print("Error while fetching project details :- ",data.json().get('message_list',
                                     data.json().get('error_detail', data.json())))
        exit(1)

def wait_for_completion(data):
    if data.ok:
        state = data.json()['status'].get('state')
        while state == "DELETE_PENDING":
            _uuid = data.json()['status']['execution_context']['task_uuid']
            url = _build_url(scheme="https",
                             resource_type="/tasks/%s"%_uuid)
            responce = requests.get(url, auth=HTTPBasicAuth(pc_username, pc_password), 
                                    verify=False)
            if responce.json()['status'] in ['DELETE_PENDING']:
                state = 'DELETE_PENDING'
                sleep(5)                
            elif responce.json()['status'] == 'FAILED':
                print("Got Error ---> ",responce.json().get('message_list', 
                                        responce.json().get('error_detail', responce.json())))
                state = 'FAILED'
                exit(1)
            else:
                state = "COMPLETE" 
    else:
        print("Got Error ---> ",data.json().get('message_list', 
                                data.json().get('error_detail', data.json())))
        exit(1)
        
def _get_ip(IP):
    ip_list = IP.split(".")
    gatewat_digit = int(ip_list[-1]) + 1
    start_digit = gatewat_digit + 1
    end_digit = start_digit + 50
    gateway_ip = ip_list[:3]
    gateway_ip.append(str(gatewat_digit))
    gateway_ip = ".".join(gateway_ip)
    start_ip = ip_list[:3]
    start_ip.append(str(start_digit))
    start_ip = ".".join(start_ip)
    end_ip = ip_list[:3]
    end_ip.append(str(end_digit))
    end_ip = ".".join(end_ip)
    return (gateway_ip, start_ip, end_ip)
    
external_subnet_items = {}
vpc_items = {}
overlay_subnet_items = {}
project_items = {}
AD_items = {}
account_items = {}

tenant = "@@{tenant_name}@@".strip()
cluster = "@@{cluster_name}@@".strip()
cluter_uuid = _get_cluster_details(cluster)
external_subnet = "@@{external_subnet_ip}@@".strip()
external_subnet_ip, external_subnet_prefix= external_subnet.split("/")
external_subnet_items['name'] = "@@{tenant_name}@@_External_Subnet"
external_subnet_items['cluster'] = cluster
external_subnet_items['enable_nat'] = @@{external_subnet_nat}@@
external_subnet_items['virtual_switch_name'] = "@@{virtual_switch}@@".strip()
_uuid = _get_virtual_switch_uuid(external_subnet_items['virtual_switch_name'], cluter_uuid)
external_subnet_items['gateway_ip'] = "@@{external_subnet_gateway_ip}@@".strip()
external_subnet_items['network_ip'] = external_subnet_ip
external_subnet_items['prefix'] = int(external_subnet_prefix)
IP_POOL = "@@{external_subnet_ip_pool}@@".strip().split("-")
external_subnet_items['ip_pools'] = {"range":"%s %s"%(IP_POOL[0],IP_POOL[1])}

vpc_items['name'] = "@@{tenant_name}@@_VPC"
vpc_items['external_subnet_name'] = external_subnet_items['name']

overlay_subnet = "@@{overlay_subnet_ip}@@".strip()
overlay_subnet_ip, overlay_subnet_prefix = overlay_subnet.split("/")
overlay_subnet_items['subnet_name'] = "@@{tenant_name}@@_Overlay_Subnet"
overlay_subnet_items['vpc_name'] = vpc_items['name']
overlay_subnet_items['network_ip'] = overlay_subnet_ip
overlay_subnet_items['prefix'] = int(overlay_subnet_prefix)
overlay_subnet_items['gateway_ip'] = "@@{overlay_subnet_gateway_ip}@@".strip()
IP = _get_ip(overlay_subnet_ip)
overlay_subnet_items['ip_pool'] = [{"ip_pools_start_ip":IP[1], 
                                     "ip_pools_end_ip":IP[2]}]
print("project_subnet_address={}".format(IP[2]))

AD_items['name'] = "Tenant_{}_AD".format(tenant)
AD_items['directory_url'] = "@@{active_directory_url}@@".strip()
AD_items['domain_name'] = "@@{active_directory_domain}@@".strip()
AD_items['directory_type'] = "ACTIVE_DIRECTORY"
AD_items['service_account_username'] = "@@{active_directory_user}@@".strip()
AD_items['service_account_password'] = "@@{active_directory_password}@@".strip()
for x in ['directory_url', 'domain_name', 'directory_type' , 
        'service_account_username', 'service_account_password']:
    if (AD_items[x] == "NA") or (AD_items[x] == ""):
        print("Input Error :- All Active Directory config parameters are mandatory. "\
            "Even if Active Directory alredy created, Need all AD details to "\
            "whitelist correct active directory for Project.")
        print("AD Parameters :- Active Directory URL, Active Directory Domain Name, "\
            "Active Directory Username, Active Directory Password.")
        exit(1)
        
admin_user = "@@{project_admin_user}@@".strip()
project_subnet_uuid = ""
project_items['name'] = "{}_project".format(tenant)
project_items['tenant_users'] =  [{"admin": ["{}".format(admin_user)]}]
project_items['accounts'] = "@@{account_name}@@".strip()
project_items['allow_collaboration'] = False
#project_subnet = "@@{project_subnet_uuid}@@"
#get_subnet_details(project_subnet)
#print("project_subnet_uuid={}".format(project_subnet))
#project_items['subnets'] = ["{}".format(project_subnet)]
project_items['quotas'] = [{'storage_gb':@@{project_disk_size}@@,
                            'mem_gb':@@{project_memory}@@,
                            'vcpu':@@{project_vcpu}@@}]

account_items['cluster'] = cluster
account_items['quotas'] = [{'storage_gb':@@{project_disk_size}@@,
                            'mem_gb':@@{project_memory}@@,
                            'vcpu':@@{project_vcpu}@@}]

print("external_subnet_items={}".format(external_subnet_items))
print("vpc_items={}".format(vpc_items))
print("overlay_subnet_items={}".format(overlay_subnet_items))
print("project_items={}".format(project_items))
print("AD_items={}".format(AD_items))
print("account_items={}".format(account_items))

def _delete(type, uuid):
    url = _build_url(scheme="https",resource_type="/%s/%s"%(type,_uuid))
    data = requests.delete(url, auth=HTTPBasicAuth(pc_username, pc_password),
                           timeout=None, verify=False)
    if not data.ok:
        print("Failed to delete existing %s with uuid %s."%(type, uuid))
        print("Error :- ",data.json())
        exit(1)
    else:
        wait_for_completion(data)
        
if "@@{delete_existing}@@".lower() == "yes":
    _uuid = _get_project_uuid(project_items['name'])
    if skip_delete == False:
        _delete(type="projects", uuid=_uuid)
        
    _uuid = _get_subnet_uuid(subnet=overlay_subnet_items['subnet_name'], delete=True)
    if skip_delete == False:
        _delete(type="subnets", uuid=_uuid)
        sleep(5)
    
    _uuid = _get_vpc_uuid(vpc_items['name'])
    if skip_delete == False:
        _delete(type="vpcs", uuid=_uuid)
        sleep(5)
        
    _uuid = _get_subnet_uuid(subnet=external_subnet_items['name'], delete=True)
    if skip_delete == False:
        _delete(type="subnets", uuid=_uuid)
