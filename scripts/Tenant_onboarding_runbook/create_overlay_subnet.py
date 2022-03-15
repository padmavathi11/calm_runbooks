#script

import requests
from requests.auth import HTTPBasicAuth
from base64 import b64encode

def _build_url(host, scheme, resource_type, **params):
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

def _get_vpc_details(vpc_name):
    for vpc in @@{vpc_details}@@:
        if vpc['name'] == vpc_name:
            _vpc = {"kind": "vpc", "uuid": vpc['uuid']}
            return _vpc

def _get_virtual_switch_uuid(virtual_switch_name):
    payload = {"entity_type": "distributed_virtual_switch", 
               "filter": "name==%s"%virtual_switch_name}
    url = _build_url(host=@@{PC_IP}@@,
                    scheme="https",
                    resource_type="/groups")                
    data = requests.post(url, json=payload,
                         auth=HTTPBasicAuth(@@{prism_central_username}@@, @@{prism_central_passwd}@@),
                         verify=False)
    if data.ok:
        print("virtual switch uuid ----> ",data.json()['group_results'][0]['entity_results'][0]['entity_id'])
        return str(data.json()['group_results'][0]['entity_results'][0]['entity_id'])
    else:
        print("Failed to get %s virtual switch uuid."%virtual_switch_name)
        exit(1)
  
def _get_cluster_details(cluster_name):
    cluster_details = {'kind':'cluster'}
    payload = {"entity_type": "cluster", "filter": "name==%s"%cluster_name}
    url = _build_url(host=@@{PC_IP}@@,
                    scheme="https",
                    resource_type="/groups")
    data = requests.post(url, json=payload,
                         auth=HTTPBasicAuth(@@{prism_central_username}@@, @@{prism_central_passwd}@@), 
                         verify=False)
    if data.ok:
        cluster_details['uuid'] = str(data.json()['group_results'][0]['entity_results'][0]['entity_id'])
        return cluster_details
    else:
        print("Failed to get %s cluster uuid."%cluster_name)
        exit(1)

def _get_default_spec():
    return (
        {
          "api_version": "3.1.0",
          "metadata": {"kind": "subnet"},
          "spec": {
                  "name": "",
                  "resources": {
                      "ip_config": {},
                      "subnet_type": None,
                      },
                  },
              }
          )

def _get_ipam_spec(**params):
    ipam_spec = {}
    if params['set_ipam'] == 'yes':
        ipam_spec = _get_default_ipconfig_spec()
        ipam_config = params["ipam"]
        ipam_spec["subnet_ip"] = ipam_config["network_ip"]
        ipam_spec["prefix_length"] = ipam_config["network_prefix"]
        ipam_spec["default_gateway_ip"] = ipam_config["gateway_ip"]
        pools = []
        if params['dhcp'] != 'None':
            for ip_pools in params['dhcp']:
                pools.append({"range": "%s %s"%(ip_pools['ip_pools_start_ip'], 
                                                ip_pools['ip_pools_end_ip'])})                                
            ipam_spec["pool_list"] = pools
        if "dhcp_options" in ipam_config:
            dhcp_spec = _get_default_dhcp_spec()
            dhcp_config = ipam_config["dhcp_options"]
            if dhcp_config['domain_name_server_list'] != 'NA': 
                dhcp_spec["domain_name_server_list"] = dhcp_config["domain_name_server_list"]
            if dhcp_config["domain_search_list"] != 'NA':
                dhcp_spec["domain_search_list"] = dhcp_config["domain_search_list"]
            if dhcp_config["domain_name"] != 'NA':
                dhcp_spec["domain_name"] = dhcp_config["domain_name"]
            if dhcp_config["boot_file_name"] != 'NA':
              dhcp_spec["boot_file_name"] = dhcp_config["boot_file_name"]
            if dhcp_config["tftp_server_name"] != 'NA':
                dhcp_spec["tftp_server_name"] = dhcp_config["tftp_server_name"]
            ipam_spec["dhcp_options"] = dhcp_spec
    return ipam_spec

def _get_default_ipconfig_spec():
    return (
        {
         "subnet_ip": None,
         "prefix_length": None,
         "default_gateway_ip": None,
         "pool_list": [],
        }
      )

def _get_default_dhcp_spec():
    return (
      {
        "domain_name_server_list": [],
        "domain_search_list": [],
        "domain_name": "",
                "boot_file_name": "",
                "tftp_server_name": "",
       }
    )

def wait_for_completion(data):
    if data.status_code in [200, 202]:
        state = data.json()['status'].get('state')
        while state == "PENDING":
            _uuid = data.json()['status']['execution_context']['task_uuid']
            url = _build_url(host=@@{PC_IP}@@,
                        scheme="https",
                        resource_type="/tasks/%s"%_uuid)
            responce = requests.get(url, auth=HTTPBasicAuth(@@{prism_central_username}@@, @@{prism_central_passwd}@@), 
                                    verify=False)
            if responce.json()['status'] in ['PENDING', 'RUNNING', 'QUEUED']:
                state = 'PENDING'
                sleep(5)                
            elif responce.json()['status'] == 'FAILED':
                print("Got error while creating subnet ---> ",responce.json())
                state = 'FAILED'
                exit(1)
            else:
                state = "COMPLETE"
    else:
        state = data.json().get('state')
        print("Got %s while creating subnet ---> "%state, data.json())
        exit(1)
    return data.json()['status']['execution_context']['task_uuid']  
    
def overlay_subnet():
    params = {}
    params['operation'] = @@{operation}@@
    if params['operation'] == "delete":
        exit(0)
    else:
        _params = @@{overlay_subnet_items}@@
        overlay_subnet_details = []
        for x in range(len(_params)):
            print("##### Creating Overlay Subnets #####")
            sleep(2)
            params_dict = _params[x]
            params['operation'] = @@{operation}@@
            params['vpc_name'] = params_dict.get('vpc_name', 'None')
            params['ipam'] = {}
            params['set_ipam'] = "yes"
            params['ipam']['network_ip'] = params_dict.get('network_ip', 'None')
            params['ipam']['network_prefix'] = params_dict.get('prefix', 'None')
            params['ipam']['gateway_ip'] = params_dict.get('gateway_ip', 'None')
            params['dhcp'] = params_dict.get('dhcp', 'None')
            params['ipam']['dhcp_options'] = {}
            params['ipam']['dhcp_options']['domain_name_server_list'] = params_dict.get('dns_servers', 'None')
            params['ipam']['dhcp_options']['domain_search_list'] = params_dict.get('domain_search', 'None')
            params['ipam']['dhcp_options']['domain_name'] = params_dict.get('domain_name', 'None')
            params['ipam']['dhcp_options']['boot_file_name'] = params_dict.get('boot_file', "NA")
            params['ipam']['dhcp_options']['tftp_server_name'] = params_dict.get('tftp_server', "NA")
            
            payload = _get_default_spec()
            if params_dict.get('vpc_name', 'None') != 'None':
                params['vpc_reference'] = _get_vpc_details(params['vpc_name'])
                payload["spec"]["resources"]["vpc_reference"] = params['vpc_reference']
            payload["spec"]['name'] = params_dict['subnet_name']
            payload["spec"]["resources"]["subnet_type"] = "OVERLAY"
            
            if params_dict.get('network_ip', 'None') != 'None':
                params['ipam_spec'] = _get_ipam_spec(**params)
                payload["spec"]["resources"]["ip_config"] = params['ipam_spec']

            if params['operation'] == "create":
                url = _build_url(host=@@{PC_IP}@@,
                        scheme="https",
                        resource_type="/subnets")    
                data = requests.post(url, json=payload,
                         auth=HTTPBasicAuth(@@{prism_central_username}@@, @@{prism_central_passwd}@@),
                         timeout=None, verify=False)
                task_uuid = wait_for_completion(data)
                details = {"uuid":data.json()['metadata']['uuid'],
                               "name": params_dict['subnet_name'],
                               "create_subnet_task_uuid": task_uuid}
                overlay_subnet_details.append(details)
        print("overlay_subnet_details={}".format(overlay_subnet_details))
overlay_subnet()
