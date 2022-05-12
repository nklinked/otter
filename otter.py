import logging
import sys
import argparse
import yaml
from components.tools.cleaner import Cleaner
from components.tools.client import Client
from components.controller.controller import Controller
from components.tools.collector import Collector

with open("./config.yaml", 'r', encoding='utf-8') as config_stream:
    try:
        config = yaml.safe_load(config_stream)
        client = Client(config)
    except yaml.YAMLError as exc:
        print(exc)
        sys.exit(1)

log_file = client.resolve_file('logs', 'run.log')
file_handler = logging.FileHandler(filename=log_file)
stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [file_handler, stdout_handler]
target_level = client.get_configured_logging_level()

logging.basicConfig(
    level=target_level,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    handlers=handlers
)

argparser = argparse.ArgumentParser()

#
# Basic connection details
#
argparser.add_argument('-a', '--api-endpoint', action='store',
                       dest='api', help='Controller API endpoint', required=True)

argparser.add_argument('-u', '--username', action='store',
                       dest='username', help='Username', required=True)

argparser.add_argument('-p', '--password', action='store',
                       dest='password', help='Password', required=True)

argparser.add_argument('-o', '--organization',
                       action='store', dest='org', help='Organization', required=True)

argparser.add_argument('-s', '--space', action='store',
                       dest='space', help='Space')

#
# Selection criteria for applications, e.g., for the router logs collection
#
argparser.add_argument('-app', '--application', action='store',
                       dest='app', help='Application')
argparser.add_argument('-exclist', '--exclusion-list-name', action='store',
                       dest='exclist', help='List of the excluded objects from config.yaml')

#
# System-wide reports, not dependent on the provided organization and space
#
argparser.add_argument('-rdb', '--report-databases', action='store_true',
                       help='[REPORT] Store general information about database tenants in a CSV file')

argparser.add_argument('-rii', '--report-invalid-instances', action='store_true',
                       help='[REPORT] Store information about inconsistent HANA service instances known by HANA Broker in a CSV file')

argparser.add_argument('-rora', '--report-org-roles-assignment', action='store_true',
                       help='[REPORT] Store information about Organization roles (OrgManager, OrgAuditor) assigned to users in a CSV file')

argparser.add_argument('-rsra', '--report-space-roles-assignment', action='store_true',
                       help='[REPORT] Store information about Space roles (SpaceManager, SpaceAuditor, SpaceDeveloper) assigned to users in a CSV file')

argparser.add_argument('-rrca', '--report-role-collections-assignment', action='store_true',
                       help='[REPORT] Store information about Role Collections assigned to users in a CSV file')

#
# Selective reports, dependent on the provided organization and space
#
argparser.add_argument('-rai', '--report-application-instances', action='store_true',
                       help='[REPORT] Store detailed information about applications in a CSV file')

argparser.add_argument('-rsi', '--report-service-instances', action='store_true',
                       help='[REPORT] Store detailed information about service instances in a CSV file')

argparser.add_argument('-rupsi', '--report-user-provided-service-instances', action='store_true',
                       help='[REPORT] Store detailed information about user-provided service instances in a CSV file')

argparser.add_argument('-rsk', '--report-service-keys', action='store_true',
                       help='[REPORT] Store information about service instances and keys in a CSV file')

argparser.add_argument('-rca', '--report-crashing-apps', action='store_true',
                       help='[REPORT] Store information about continuously crashing applications in a CSV file')

argparser.add_argument('-rnmo', '--report-non-mta-objects', action='store_true',
                       help='[REPORT] Store information about applications and service instances, having no MTA information, in a CSV file')

argparser.add_argument('-rpal', '--report-parsed-app-log', action='store_true',
                       help='[REPORT] Store the parsed application log, having only RTR entries, in a CSV file')

#
# Operations
#

argparser.add_argument('-sca', '--stop-crashing-apps', action='store_true',
                       help='[OPERATION] [EXPERIMENTAL] [MUST HAVE EXCLUSION LIST] Stop continuously crashing applications')

argparser.add_argument('-dscai', '--delete-stopped-crashed-app-instances', action='store_true',
                       help='[OPERATION] [EXPERIMENTAL] [MUST HAVE EXCLUSION LIST] Delete stopped and crashed application instances')

argparser.add_argument('-dnmasi', '--delete-non-mta-apps-and-service-instances', action='store_true',
                       help='[OPERATION] [EXPERIMENTAL] [MUST HAVE EXCLUSION LIST] Delete applications and service instances, having no MTA information')

#
# Commands
#
args = argparser.parse_args()

logging.info(
    f'Working with XS Advanced Controller Endpoint: {args.api} and user {args.username}')

controller = Controller(args.api, args.username, args.password)
collector = Collector(controller, client)
cleaner = Cleaner(controller, collector, client)

#
# System-wide commands, not dependent on the provided organization and space
#

if args.report_databases:
    logging.info(
        'Storing general information about database tenants in a CSV file')
    collector.store_databases()

if args.report_invalid_instances:
    logging.info(
        'Storing information about inconsistent HANA service instances known by HANA Broker in a CSV file')
    collector.store_invalid_instances()

if args.report_org_roles_assignment:
    logging.info(
        'Storing information about Organization roles (OrgManager, OrgAuditor) assigned to users in a CSV file')
    collector.store_org_roles_assignment()

if args.report_space_roles_assignment:
    logging.info(
        'Storing information about Space roles (SpaceManager, SpaceAuditor, SpaceDeveloper) assigned to users in a CSV file')
    collector.store_space_roles_assignment()

if args.report_role_collections_assignment:
    logging.info(
        'Storing information about Role Collections assigned to users in a CSV file')
    collector.store_role_collections_assignment()

#
# Selective commands, dependent on the provided organization and space
#

if (args.report_application_instances or
     args.report_service_instances or
     args.report_user_provided_service_instances or
     args.report_service_keys or
     args.report_crashing_apps or
     args.report_non_mta_objects):

    org_space_guids = collector.get_target_org_space_guids_by_name(args.org, space_name=args.space)
    for couple in org_space_guids:
        org_guid, space_guid = couple
        org = controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        logging.info(f'Working with organization {org.name} / {org_guid} and space {space.name} / {space_guid}')

        if args.report_application_instances:
            logging.info('Storing detailed information about applications in a CSV file')
            collector.store_applications(org_guid, space_guid)

        if args.report_service_instances:
            logging.info('Storing detailed information about service instances in a CSV file')
            collector.store_service_instances(org_guid, space_guid)
        
        if args.report_user_provided_service_instances:
            logging.info('Storing detailed information about user-provided service instances in a CSV file')
            collector.store_ups_service_instances(org_guid, space_guid)

        if args.report_service_keys:
            logging.info('Storing information about service instances and keys in a CSV file')
            collector.store_service_instance_keys(org_guid, space_guid)

        if args.report_crashing_apps:
            logging.info('Storing information about continuously crashing applications in a CSV file')
            collector.store_continuously_crashing_apps(org_guid, space_guid)

        if args.report_non_mta_objects:
            logging.info('Storing information about applications and service instances, having no MTA information, in a CSV file')
            collector.store_non_mta_apps_service_instances(org_guid, space_guid)


if args.report_parsed_app_log:
    org_space_app_guids = collector.get_target_org_space_app_guids_by_name(args.org, space_name=args.space, app_name=args.app)

    for triple in org_space_app_guids:
        org_guid, space_guid, app_guid = triple
        org = controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        app = space.get_app_by_guid(app_guid)

        logging.info(f'Storing the router log of application {app.name} / {app_guid} from org {org.name} / {org_guid} and space {space.name} / {space_guid}')
        collector.store_app_router_log(org_guid, space_guid, app_guid)

#
# Selective operations, dependent on the provided organization and space
#

if (args.stop_crashing_apps or
     args.delete_stopped_crashed_app_instances or
     args.delete_non_mta_apps_and_service_instances):

    org_space_guids = collector.get_target_org_space_guids_by_name(args.org, space_name=args.space)
    for couple in org_space_guids:
        org_guid, space_guid = couple
        org = controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        logging.info(f'Working with organization {org.name} / {org_guid} and space {space.name} / {space_guid}')

        if args.stop_crashing_apps:
            cleaner.stop_continuously_crashing_apps(org_guid, space_guid, exclusion_list_name=args.exclist)

        if args.delete_stopped_crashed_app_instances:
            cleaner.delete_app_instances_by_state(org_guid, space_guid, exclusion_list_name=args.exclist, target_states=['STOPPED', 'CRASHED'])

        if args.delete_non_mta_apps_and_service_instances:
            cleaner.delete_non_mta_app_service_instances(org_guid, space_guid, exclusion_list_name=args.exclist)