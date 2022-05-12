import logging
import json
import re
from components.tools.utils import epoch_to_datetime # pylint: disable=import-error


class Application:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, space, raw_data):
        logging.debug(('Loading the application information '
                       f'based on {raw_data} from space {space.name} / {space.guid}'))

        self.space = space
        self.controller = self.space.controller
        self.controller_session = self.controller.controller_session

        self._instances = {}
        self._tasks = {}
        self._monitoring_data = {}
        self._routes = {}
        self._representation = None

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)

        application_entity = raw_data.get('applicationEntity')
        self.name = application_entity.get('name')
        self.detected_buildpack = application_entity.get('detected_buildpack')
        self.state = application_entity.get('state')
        self.memory = application_entity.get('memory')
        self.planned_instances_count = application_entity.get('instances')

        service_bindings = self.space.service_bindings
        self.service_bindings = list(service_bindings[guid] for guid in service_bindings
                                     if service_bindings[guid].bound_app_guid == self.guid)
        self.count_bindings = len(self.service_bindings)

        self.logs = ApplicationLogs(self)

        # Environmental information
        def get_env_value_by_key(environment, key):
            return next((var.get('value') for var in environment if var.get('key') == key), None)

        environment = application_entity.get('environment')

        # Information about the MTA if the application belongs to one
        mta_metadata = get_env_value_by_key(environment, 'MTA_METADATA')
        self.mta_id = json.loads(mta_metadata).get('id') if mta_metadata else None
        self.mta_version = json.loads(mta_metadata).get('version') if mta_metadata else None

        # Information about the MTA module if the application is the one
        mta_module_metadata = get_env_value_by_key(environment, 'MTA_MODULE_METADATA')
        self.mta_module_name = (json.loads(mta_module_metadata).get('name')
                                if mta_module_metadata
                                else None)

        # Information about dependencies provided by MTA if the application belongs to one
        mta_module_dependencies = get_env_value_by_key(environment,
                                                       'MTA_MODULE_PROVIDED_DEPENDENCIES')
        self.mta_module_dependencies = (json.loads(mta_module_dependencies)
                                        if mta_module_dependencies
                                        else None)

        # Information about services provided by MTA if the application belongs to one
        mta_services = get_env_value_by_key(environment, 'MTA_SERVICES')
        self.mta_services = json.loads(mta_services) if mta_services else None

        # Information about the application target runtime if it is provided
        self.target_runtime = get_env_value_by_key(environment, 'TARGET_RUNTIME')

        # Information about the Database Schema. Usually it is provided for HDI deployers
        self.target_container = get_env_value_by_key(environment, 'TARGET_CONTAINER')

        self.belongs_to_mta = (bool(mta_metadata)
                               | bool(mta_module_metadata)
                               | bool(mta_module_dependencies)
                               | bool(mta_services))

        self.has_deployment_tasks = bool(next((task for task in self.tasks
                                               if self.tasks[task].is_deployment_task), None))

        self.is_hdi_deployer = (self.has_deployment_tasks
                                | bool(self.target_container))

        # Monitoring information
        self.running_instances_count = self.monitoring_data.get('total_running')
        self.crashed_instances_count = self.monitoring_data.get('total_crashed')
        self.crashed_short_term_count = self.monitoring_data.get('crashed_short_term')
        self.crashed_mid_term_count = self.monitoring_data.get('crashed_mid_term')
        self.crashed_long_term_count = self.monitoring_data.get('crashed_long_term')
        self.down = self.monitoring_data.get('down')
        self.uptime = self.monitoring_data.get('uptime')

        logging.info((f'Loaded information about application {self.name} / {self.guid} '
                      f'from space {self.space.name} / {self.space.guid}'))

    #
    # Lazy load application instances
    #
    @property
    def instances(self):
        return self._instances

    @instances.getter
    def instances(self):
        controller_session = self.controller_session
        if not self._instances:
            try:
                instances_info = controller_session.get(f'/v2/apps/{self.guid}/instances')
                instances = instances_info.get('response_body').get('instances')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    f'Failed to fetch instances of application {self.name} / {self.guid}',
                    exc_info=e)
                raise
            else:
                parsed_instances = {}
                for instance in instances:
                    instance_guid = instance.get('metadata').get('guid')
                    parsed_instances[instance_guid] = ApplicationInstance(self, instance)
                self._instances = parsed_instances
                logging.debug((f'Loaded the information about instances of application '
                               f'{self.name} / {self.guid}'))
        return self._instances

    @instances.setter
    def instances(self, instances):
        self._instances = instances

    #
    # Lazy load application tasks
    #
    @property
    def tasks(self):
        return self._tasks

    @tasks.getter
    def tasks(self):
        controller_session = self.controller_session
        if not self._tasks:
            try:
                tasks_info = controller_session.get(f'/v2/apps/{self.guid}/tasks')
                tasks = tasks_info.get('response_body').get('tasks')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    f'Failed to fetch tasks of application {self.name} / {self.guid}',
                    exc_info=e)
                raise
            else:
                parsed_tasks = {}
                for task in tasks:
                    task_guid = task.get('metadata').get('guid')
                    parsed_tasks[task_guid] = ApplicationTask(self, task)
                self._tasks = parsed_tasks
                logging.debug(('Loaded the information about tasks of application '
                               f'{self.name} / {self.guid}'))
        return self._tasks

    @tasks.setter
    def tasks(self, tasks):
        self._tasks = tasks

    #
    # Lazy load the application monitoring data
    #
    @property
    def monitoring_data(self):
        return self._monitoring_data

    @monitoring_data.getter
    def monitoring_data(self):
        controller_session = self.controller_session
        if not self._monitoring_data:
            try:
                monitoring_data_info = controller_session.get(
                                            f'/v2/monitoring/status/apps/{self.guid}')
                monitoring_data = monitoring_data_info.get('response_body')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    f'Failed to fetch the monitoring data of application {self.name} / {self.guid}',
                    exc_info=e)
                raise
            else:
                self._monitoring_data = monitoring_data
                logging.debug(
                    f'Loaded the monitoring data of application {self.name} / {self.guid}')
        return self._monitoring_data

    @monitoring_data.setter
    def monitoring_data(self, monitoring_data):
        self._monitoring_data = monitoring_data

    #
    # Represent the application for the Collector
    #
    @property
    def representation(self):
        return self._representation

    @representation.getter
    def representation(self):
        return (self.space.org.guid,
                self.space.org.name,
                self.space.guid,
                self.space.name,
                self.guid,
                self.name,
                self.target_runtime,
                self.detected_buildpack,
                self.created_at,
                self.updated_at,
                self.state,
                self.down,
                self.uptime,
                self.memory,
                self.mta_module_name,
                self.mta_id,
                self.mta_version,
                self.mta_module_dependencies,
                self.mta_services,
                self.count_bindings,
                self.target_container,
                self.belongs_to_mta,
                self.has_deployment_tasks,
                self.is_hdi_deployer,
                self.planned_instances_count,
                self.running_instances_count,
                self.crashed_instances_count,
                self.crashed_short_term_count,
                self.crashed_mid_term_count,
                self.crashed_long_term_count)

    #
    # Lazy load the application routes
    #
    @property
    def routes(self):
        return self._routes

    @routes.getter
    def routes(self):
        controller_session = self.controller_session
        if not self._routes:
            try:
                routes_info = controller_session.get(f'/v2/apps/{self.guid}/routes')
                routes = routes_info.get('response_body').get('routes')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    f'Failed to load routes of application {self.name}', exc_info=e)
                raise
            else:
                parsed_routes = {}
                for route in routes:
                    route_guid = route.get('metadata').get('guid')
                    parsed_routes[route_guid] = ApplicationRoute(self, route)
                self._routes = parsed_routes
                logging.debug(f'Loaded routes of application {self.name} / {self.guid}')
        return self._routes

    @routes.setter
    def routes(self, routes):
        self._routes = routes

    @staticmethod
    def get_representation_keys():
        return ['Org GUID',
                'Org Name',
                'Space GUID',
                'Space Name',
                'App GUID',
                'App Name',
                'Target Runtime',
                'Detected Buildpack',
                'Created At',
                'Updated At',
                'State',
                'Is Down',
                'Uptime *100%',
                'Memory',
                'MTA Module Name',
                'MTA ID',
                'MTA Version',
                'MTA Module Dependencies',
                'MTA Services',
                'Count of Bindings',
                'Target Container (hdi-deploy)',
                'Belongs to MTA',
                'Has Deployment Tasks',
                'Is HDI Deployer',
                'Planned Instances Count',
                'Running Instances Count',
                'Crashed Instances Count',
                'Short-Term Crashes Count',
                'Mid-Term Crashes Count',
                'Long-Term Crashes Count']


class ApplicationInstance:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, app, raw_data):
        self.app = app
        self._representation = None

        metadata = raw_data.get('metadata')
        instance_entity = raw_data.get('instanceEntity')
        self.guid = metadata.get('guid')
        self.droplet = instance_entity.get('droplet')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)
        self.started_at = (epoch_to_datetime(instance_entity.get('started_at'))
                           if instance_entity.get('started_at')
                           else None)
        self.state = instance_entity.get('state')
        self.failure_reason = instance_entity.get('failure_reason')
        self.pid = instance_entity.get('pid')
        self.execution_user = instance_entity.get('execution_user')

        logging.debug((f'Loaded the information about instance {self.guid} '
                       f'of application {self.app.name} / {self.app.guid}'))

    #
    # Represent the application instance for the Collector
    #
    @property
    def representation(self):
        return self._representation

    @representation.getter
    def representation(self):
        return (self.guid,
                self.droplet,
                self.started_at,
                self.created_at,
                self.updated_at,
                self.state,
                self.failure_reason,
                self.pid,
                self.execution_user)

    @staticmethod
    def get_representation_keys():
        return ['Instance GUID',
                'Instance Droplet GUID',
                'Instance Started At',
                'Instance Created At',
                'Instance Updated At',
                'Instance State',
                'Instance Failure Reason',
                'Instance PID',
                'Instance OS User']

    @staticmethod
    def get_blank_representation():
        return (None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None)


class ApplicationTask:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    def __init__(self, app, raw_data):
        self.app = app
        metadata = raw_data.get('metadata')
        task_entity = raw_data.get('taskEntity')
        self.guid = metadata.get('guid')
        self.name = task_entity.get('name')
        self.command = task_entity.get('command')
        self.instance_guid = task_entity.get('instance_guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('created_at')
                           else None)
        self.state = task_entity.get('state')
        self.task_result = task_entity.get('task_result')

        def recognized_as_deployment_task(name, start_command, environment_vars):
            has_relevant_vars = bool(next((var for var in environment_vars
                                           if var.get('key') == 'HDI_DEPLOY_OPTIONS'), None))

            has_deployer_reference = (('/@sap/hdi-deploy/deploy.js' in start_command)
                                      | ('@sap/site-content-deployer/deploy' in start_command))

            has_deployer_command = ((name == 'deploy')
                                    and (start_command == 'npm start'))
            at_least_one = (has_relevant_vars
                            | has_deployer_reference
                            | has_deployer_command)
            return at_least_one

        self.is_deployment_task = recognized_as_deployment_task(self.name,
                                                                self.command,
                                                                task_entity.get(
                                                                    'environment_variables'))

        logging.debug((f'Loaded the information about task {self.guid} '
                       f'of application {self.app.name} / {self.app.guid}'))


class ApplicationLogs:
    def __init__(self, app):
        self.app = app
        self.controller_session = self.app.controller_session
        self._complete_log = []
        self._router_log = []
        self._parsed_router_log = []
        self._router_log_representation = None

    #
    # Lazy load the router application log
    #
    @property
    def router_log(self):
        return self._router_log

    @router_log.getter
    def router_log(self):
        controller_session = self.controller_session
        if not self._router_log:
            params = {'q': 'tag IN RTR;',
                      'since': 0,
                      'startLine': 0,
                      'maxLines': 1000000000}
            try:
                router_log_info = controller_session.get(f'/v2/apps/{self.app.guid}/logs',
                                                         params=params)
                router_log = router_log_info.get('response_body')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    f'Failed to fetch the log from application {self.app.name} / {self.app.guid}',
                    exc_info=e)
                raise
            else:
                self._router_log = router_log
                logging.debug(
                    f'Loaded the router log (RTR) of application {self.app.name} / {self.app.guid}')
        return self._router_log

    @router_log.setter
    def router_log(self, router_log):
        self._router_log = router_log

    #
    # Lazy parse the router application log
    #
    @property
    def parsed_router_log(self):
        return self._parsed_router_log

    @parsed_router_log.getter
    def parsed_router_log(self):
        if not self._parsed_router_log:
            if self.router_log:
                parsed_router_log = []
                for line in self.router_log:
                    line_pattern = r'^\(\d+\)\[(\d+)\] \[RTR\] OUT (.*) - - to (.*) (".*") (.+) sent (.+) in (.+) by .+$' # pylint: disable=line-too-long
                    parsed_line = re.match(line_pattern, line)

                    if parsed_line:
                        parsed_entry = {'timestamp': epoch_to_datetime(parsed_line.group(1)),
                                        'caller': parsed_line.group(2),
                                        'callee': parsed_line.group(3),
                                        'method': None,
                                        'request_string': None,
                                        'http_status': (parsed_line.group(5)
                                                        if parsed_line.group(5).isdigit()
                                                        else None),
                                        'response_size': (parsed_line.group(6)
                                                          if parsed_line.group(6).isdigit()
                                                          else None),
                                        'response_time': (parsed_line.group(7)
                                                          if parsed_line.group(7).isdigit()
                                                          else None)}

                        source_request = parsed_line.group(4)
                        request_pattern = r'^"(POST|GET|PUT|PATCH|DELETE|HEAD|CONNECT|OPTIONS|TRACE) (\/.*) HTTP.*|"- - -"$' # pylint: disable=line-too-long
                        parsed_request = re.match(
                            request_pattern, source_request)
                        if parsed_request:
                            descriptive_request_patter = r'"(POST|GET|PUT|PATCH|DELETE|HEAD|CONNECT|OPTIONS|TRACE) (\/.*) HTTP.*"' # pylint: disable=line-too-long
                            descriptive_request = re.match(descriptive_request_patter,
                                                           source_request)
                            parsed_entry['method'] = (descriptive_request.group(1)
                                                      if descriptive_request
                                                      else None)
                            parsed_entry['request_string'] = (descriptive_request.group(2)
                                                              if descriptive_request
                                                              else None)
                            parsed_router_log.append(parsed_entry)
                        else:
                            logging.debug(f'Failed to parse the request string: {source_request}')
                    else:
                        logging.debug(f'Failed to parse the router log entry: {line}')
                self._parsed_router_log = parsed_router_log
                logging.debug(('Parsed the router log (RTR) of application '
                               f'{self.app.name} / {self.app.guid}'))
            else:
                self._parsed_router_log = []
        return self._parsed_router_log

    @parsed_router_log.setter
    def parsed_router_log(self, parsed_router_log):
        self._parsed_router_log = parsed_router_log
    
    #
    # Represent the router log for the Collector
    #
    @property
    def router_log_representation(self):
        return self._router_log_representation

    @router_log_representation.getter
    def router_log_representation(self):
        log_representation = []
        log = self.parsed_router_log
        for entry in log:
            log_representation.append((entry.get('timestamp'),
                                       entry.get('caller'),
                                       entry.get('callee'),
                                       entry.get('method'),
                                       entry.get('request_string'),
                                       entry.get('http_status'),
                                       entry.get('response_size'),
                                       entry.get('response_time')))
        return log_representation

    @staticmethod
    def get_router_log_representation_keys():
        return ['Timestamp',
                'Caller',
                'Callee',
                'Method',
                'Request String',
                'HTTP Status',
                'Response Size, byte',
                'Response Time, ms']


class ApplicationRoute:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    def __init__(self, app, raw_data):
        self.app = app

        metadata = raw_data.get('metadata')
        instance_entity = raw_data.get('routeEntity')

        self.guid = metadata.get('guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)

        self.space_guid = instance_entity.get('space_guid')
        self.uri = instance_entity.get('uri')
        self.domain = instance_entity.get('domain')
        self.port = instance_entity.get('port')
        self.type = instance_entity.get('type')
        self.orphaned = instance_entity.get('orphaned')

        logging.debug((f'Loaded the information about route {self.guid} / {self.uri} '
                       f'of application {self.app.name} / {self.app.guid}'))
