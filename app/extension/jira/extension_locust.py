# import re
# from locustio.common_utils import init_logger, jira_measure, run_as_specific_user  # noqa F401
#
# logger = init_logger(app_type='jira')
#
#
# @jira_measure("locust_app_specific_action")
# # @run_as_specific_user(username='admin', password='admin')  # run as specific user
# def app_specific_action(locust):
#     r = locust.get('/app/get_endpoint', catch_response=True)  # call app-specific GET endpoint
#     content = r.content.decode('utf-8')   # decode response content
#
#     token_pattern_example = '"token":"(.+?)"'
#     id_pattern_example = '"id":"(.+?)"'
#     token = re.findall(token_pattern_example, content)  # get TOKEN from response using regexp
#     id = re.findall(id_pattern_example, content)    # get ID from response using regexp
#
#     logger.locust_info(f'token: {token}, id: {id}')  # log info for debug when verbose is true in jira.yml file
#     if 'assertion string' not in content:
#         logger.error(f"'assertion string' was not found in {content}")
#     assert 'assertion string' in content  # assert specific string in response content
#
#     body = {"id": id, "token": token}  # include parsed variables to POST request body
#     headers = {'content-type': 'application/json'}
#     r = locust.post('/app/post_endpoint', body, headers, catch_response=True)  # call app-specific POST endpoint
#     content = r.content.decode('utf-8')
#     if 'assertion string after successful POST request' not in content:
#         logger.error(f"'assertion string after successful POST request' was not found in {content}")
#     assert 'assertion string after successful POST request' in content  # assertion after POST request

import random
from locustio.common_utils import init_logger, jira_measure, run_as_specific_user, raise_if_login_failed, fetch_by_re  # noqa F401
from locustio.jira.requests_params import BrowseIssue, jira_datasets


logger = init_logger(app_type='jira')
jira_dataset = jira_datasets()

BASE_PATH = '/rest/quantum/1.0/'


def search_estimated_resource(estimated_resources, resource_id):
    for keyval in estimated_resources:
        if resource_id == keyval['resourceId']:
            return keyval
    return None


def get_quick_estimation_order(estimation_orders):
    for keyval in estimation_orders:
        if keyval['estimationOrderType'] == 'USER_ESTIMATION_ORDER' and keyval['isUserAllowedToEstimate'] == True:
            return keyval
    return None


@jira_measure("locust_app_specific_action")
# @run_as_specific_user(username='admin', password='admin')  # run as specific user
def app_specific_action(locust):
    raise_if_login_failed(locust)
    params = BrowseIssue()
    issue_key = random.choice(jira_dataset['issues'])[0]

    r = locust.get(f'/browse/{issue_key}', catch_response=True)
    content = r.content.decode('utf-8')
    issue_id = fetch_by_re(params.issue_id_pattern, content)

    r = locust.get(BASE_PATH + f'estimation-panel/estimated-issue/{issue_id}', catch_response=True)
    response_json = r.json()
    if response_json['isEstimationExisting'] == False:
        r = locust.put(BASE_PATH + f'estimation/', catch_response=True, json={"issueId": issue_id})
        r = locust.get(BASE_PATH + f'estimation-panel/estimated-issue/{issue_id}', catch_response=True)
        response_json = r.json()

    assert response_json['isEstimationExisting'] == True

    estimation_id = response_json['estimationId']
    r = locust.get(BASE_PATH + f'estimation/{estimation_id}', catch_response=True)
    response_json = r.json()

    estimation_state = response_json['estimationState']

    if estimation_state == 'DISABLED':
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "QUICK_ESTIMATING"})
    elif estimation_state == 'ESTIMATION_DESIGN':
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "QUICK_ESTIMATING"})
    elif estimation_state == 'ESTIMATING':
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "REPLAN"})
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "QUICK_ESTIMATING"})
    elif estimation_state == 'FAILED':
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "REPLAN"})
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "QUICK_ESTIMATING"})
    elif estimation_state == 'ESTIMATED':
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "QUICK_ESTIMATING"})
    elif estimation_state == 'REPLAN':
        locust.patch(BASE_PATH + f'estimation/{estimation_id}', catch_response=True,
                     json={"targetEstimationState": "QUICK_ESTIMATING"})
        r = locust.get(BASE_PATH + f'estimation/{estimation_id}', catch_response=True)
        response_json = r.json()
        assert response_json['estimationState'] == 'QUICK_ESTIMATING'

    r = locust.get(BASE_PATH + f'estimation-panel/active-resources/{issue_id}', catch_response=True)
    response_json = r.json()

    assert len(response_json) > 0

    resource_id = response_json[0]['resourceId']

    r = locust.get(BASE_PATH + f'estimation/{estimation_id}/estimated-resource', catch_response=True)
    response_json = r.json()

    estimated_resource = search_estimated_resource(response_json, resource_id)

    if estimated_resource == None:
        locust.post(BASE_PATH + f'estimation/{estimation_id}/estimated_resource', catch_response=True,
                    json={'resourceId': resource_id})
        r = locust.get(BASE_PATH + f'estimation/{estimation_id}/estimated-resource', catch_response=True)
        response_json = r.json()
        estimated_resource = search_estimated_resource(response_json, resource_id)

    assert estimated_resource != None

    estimated_resource_id = estimated_resource['estimatedResourceId']

    r = locust.post(
        BASE_PATH + f'estimation-panel/estimation/{estimation_id}/estimated-resource/{estimated_resource_id}/create-quick-estimation-order',
        catch_response=True)

    r = locust.get(
        BASE_PATH + f'estimation-panel/estimation/{estimation_id}/estimated-resource/{estimated_resource_id}/estimation-order',
        catch_response=True)
    response_json = r.json()

    quick_estimation_order = get_quick_estimation_order(response_json)

    assert quick_estimation_order != None

    estimation_order_id = quick_estimation_order['estimationOrderId']

    value_set = {'pointEstimateValueSet': {'value': '10'}}

    locust.post(
        BASE_PATH + f'estimation/{estimation_id}/estimated-resource/{estimated_resource_id}/estimation-order/{estimation_order_id}/estimate',
        catch_response=True, json=value_set)