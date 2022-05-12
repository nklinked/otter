import logging
import time
from components.controller.session import ControllerSession # pylint: disable=import-error
from components.controller.database import Database # pylint: disable=import-error
from components.controller.organization import Organization # pylint: disable=import-error
from components.tools.utils import epoch_to_datetime # pylint: disable=import-error


class Controller:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, api_endpoint, user, password, **kwargs):
        try:
            self.controller_session, self.uaa_session = self.__set_controller_sessions(
                api_endpoint,
                user,
                password,
                **kwargs)

            self.hana_broker_session = self.__set_hana_broker_session(self.controller_session)

            self._databases = {}
            self._orgs = {}
            self._monitoring_config = {}
            self._app_monitoring_config = {}
            self._users = {}

        except Exception as e: # pylint: disable=invalid-name
            logging.error('Failed to instantiate Controller', exc_info=e)
            raise

    def __set_controller_sessions(self, api_endpoint, user, password, **kwargs):
        try:
            controller_session = ControllerSession(api_endpoint)
            controller_info = controller_session.get('/v2/info', **kwargs)
            authorization_endpoint = controller_info.get('response_body').get(
                'authorizationEndpoint')
        except Exception as e: # pylint: disable=invalid-name
            logging.error('Failed to load the Controller metadata', exc_info=e)
            raise
        else:
            try:
                uaa_session = ControllerSession(authorization_endpoint, **kwargs)
                uaa_session.basic_auth = ('cf', '')
                data = {'grant_type': 'password',
                        'username': user,
                        'password': password,
                        'client_id': 'cf'}
                authorization_info = uaa_session.post('/oauth/token', data=data)
                bearer_token = authorization_info.get('response_body').get('access_token')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(f'Failed to authenticate the Controller user {user}',
                              exc_info=e)
                raise
            else:
                controller_session.bearer_auth = bearer_token
                uaa_session.bearer_auth = bearer_token
                logging.info(f'Authenticated the remote Controller sessions of user {user}')
                return controller_session, uaa_session

    def __set_hana_broker_session(self, controller_session):
        try:
            brokers_info = controller_session.get('/v2/service_brokers')
            brokers = brokers_info.get('response_body').get('serviceBrokers')
            if bool(brokers):
                hana_broker = next(
                    filter(
                        lambda brokers: brokers['serviceBrokerEntity']['name'] == 'hdi-broker',
                        brokers),
                    None)
                broker_endpoint = hana_broker.get('serviceBrokerEntity').get('broker_url')
            else:
                raise Exception(
                    'Failed to fetch the information about the service brokers from Controller')
        except Exception as e: # pylint: disable=invalid-name
            logging.error('Failed to load the HANA Broker metadata', exc_info=e)
            raise
        else:
            try:
                hana_broker_info = self.controller_session.get(
                    '/v2/admin/hana_broker/credentials/admin_user')
                user = hana_broker_info.get('response_body').get('user')
                password = hana_broker_info.get('response_body').get(
                    'password')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    'Failed to load HANA Broker credentials', exc_info=e)
                raise
            else:
                broker_session = ControllerSession(broker_endpoint)
                broker_session.basic_auth = (user, password)
                logging.info('Authenticated the remote HANA Broker session')
                return broker_session

    #
    # Lazy load Controller databases
    #
    @property
    def databases(self):
        return self._databases

    @databases.getter
    def databases(self):
        hana_broker_session = self.hana_broker_session
        if not self._databases:
            try:
                databases_info = hana_broker_session.get('/admin/databases')
                databases = databases_info.get('response_body').get(
                    'databases')
            except Exception as e: # pylint: disable=invalid-name
                logging.error('Failed to fetch databases from HANA Broker',
                              exc_info=e)
                raise
            else:
                try:
                    mappings_info = hana_broker_session.get('/admin/database_mappings')
                    mappings = mappings_info.get('response_body').get('mappings')
                except Exception as e: # pylint: disable=invalid-name
                    logging.error('Failed to fetch databases mappings from HANA Broker',
                                  exc_info=e)
                    raise
                else:
                    parsed_mappings = {}
                    for mapping in mappings:
                        database_id = mapping.get('database_id')
                        if database_id not in parsed_mappings:
                            parsed_mappings[database_id] = []
                        org_guid = mapping.get('organization_guid')
                        space_guid = mapping.get('space_guid')
                        if bool(org_guid) | bool(space_guid):
                            parsed_mappings[database_id].append((org_guid, space_guid))

                    parsed_databases = {}
                    for database in databases:
                        database_id = database.get('id')
                        try:
                            database_info = hana_broker_session.get(
                                f'/admin/databases/{database_id}',
                                params={'fullData': 'True'})

                            database_metadata = database_info.get('response_body')
                        except Exception as e: # pylint: disable=invalid-name
                            logging.error((
                                'Failed to fetch the database information '
                                f'for database guid {database_id} from HANA Broker'), exc_info=e)
                            raise
                        else:
                            database_metadata['mapped_orgs_space_guids'] = parsed_mappings.get(
                                database_id)
                            parsed_databases[database_id] = Database(self, database_metadata)
                    self._databases = parsed_databases
                    logging.info('Loaded the information about databases from HANA Broker')
        return self._databases

    @databases.setter
    def databases(self, databases):
        self._databases = databases

    #
    # Lazy load Controller organizations
    #
    @property
    def orgs(self):
        return self._orgs

    @orgs.getter
    def orgs(self):
        controller_session = self.controller_session
        if not self._orgs:
            try:
                orgs_info = controller_session.get('/v2/organizations')
                orgs = orgs_info.get('response_body').get('organizations')
            except Exception as e: # pylint: disable=invalid-name
                logging.error('Failed to fetch organizations from Controller',
                              exc_info=e)
                raise
            else:
                parsed_orgs = {}
                for org in orgs:
                    org_guid = org.get('metadata').get('guid')
                    parsed_orgs[org_guid] = Organization(self, org)
                self._orgs = parsed_orgs
                logging.info('Loaded the information about organizations from Controller')
        return self._orgs

    @orgs.setter
    def orgs(self, orgs):
        self._orgs = orgs

    #
    # Lazy load the Controller app monitoring configuration
    #
    @property
    def app_monitoring_config(self):
        return self._app_monitoring_config

    @app_monitoring_config.getter
    def app_monitoring_config(self):
        controller_session = self.controller_session
        if not self._app_monitoring_config:
            try:
                app_monitoring_config_info = controller_session.get('/v2/monitoring/status')
                app_monitoring_config = app_monitoring_config_info.get('response_body')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    'Failed to fetch the application monitoring configuration from Controller',
                    exc_info=e)
                raise
            else:
                self._app_monitoring_config = {
                    'short_term_seconds': app_monitoring_config.get('short_term_seconds'),
                    'mid_term_seconds': app_monitoring_config.get('mid_term_seconds'),
                    'long_term_seconds': app_monitoring_config.get('long_term_seconds')
                }
                logging.info('Loaded the application monitoring configuration from Controller')
        return self._app_monitoring_config

    @app_monitoring_config.setter
    def app_monitoring_config(self, app_monitoring_config):
        self._app_monitoring_config = app_monitoring_config

    #
    # Lazy load the Controller platform monitoring configuration
    #
    @property
    def monitoring_config(self):
        return self._monitoring_config

    @monitoring_config.getter
    def monitoring_config(self):
        controller_session = self.controller_session
        if not self._monitoring_config:
            try:
                monitoring_config_info = controller_session.get('/v2/monitoring')
                monitoring_config = monitoring_config_info.get('response_body')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(
                    'Failed to fetch the platform monitoring configuration from Controller',
                    exc_info=e)
                raise
            else:
                self._monitoring_config = monitoring_config
                logging.info('Loaded the platform monitoring configuration from Controller')
        return self._monitoring_config

    @monitoring_config.setter
    def monitoring_config(self, monitoring_config):
        self._monitoring_config = monitoring_config

    #
    # Lazy load Controller users
    #
    @property
    def users(self):
        return self._users

    @users.getter
    def users(self):
        controller_session = self.controller_session
        if not self._users:
            try:
                users_info = controller_session.get('/v2/users')
                users = users_info.get('response_body').get('users')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error('Failed to fetch users from Controller', exc_info=e)
                raise
            else:
                parsed_users = {}
                for user in users:
                    user_guid = user.get('metadata').get('guid')
                    parsed_users[user_guid] = User(self, user)
                self._users = parsed_users
                logging.info('Loaded the information about users from Controller')
        return self._users

    @users.setter
    def users(self, users):
        self._users = users

    #
    # Controller operations applied to entities
    #

    #
    # Jobs
    #
    def get_job_status(self, job_guid, **kwargs):
        kwargs.setdefault('wait_for_finish', False)
        status = None
        try:
            if kwargs.get('wait_for_finish'):
                job_info = self.controller_session.get(f'/v2/jobs/{job_guid}/waitForFinish')
            else:
                job_info = self.controller_session.get(f'/v2/jobs/{job_guid}/observe')
        except Exception as e:  # pylint: disable=invalid-name
            logging.error(f'Failed to fetch the information about the job guid: {job_guid}',
                          exc_info=e)
            raise
        else:
            try:
                request_status = job_info.get('http_status')
                response = job_info.get('response_body')

                # Job was found and results are returned
                if request_status == 200:

                    # Check if multiple results are returned and use the last one
                    if response.get('responses'):
                        last_state = response.get('responses').pop()
                        status = last_state.get('jobEntity').get('status')
                        logging.debug((f'Identified status {status} '
                                       f'of job guid: {job_guid} based on {response}'))

                    # Check if the single result is returned and use it
                    elif response.get('jobEntity'):
                        status = response.get('jobEntity').get('status')
                        logging.debug((f'Identified status {status} '
                                       f'of job guid: {job_guid} based on {response}'))

                    else:
                        raise Exception(f'Failed to recognize the job status based on {response}')

                # Job was not found and results are not returned
                elif request_status == 404:
                    status = 'NOT FOUND'
                    logging.warning(f'Requested job was not found with job guid: {job_guid}')

                # Server error occured wher requesting the job status
                elif request_status == 500:
                    status = 'SERVER ERROR'
                    logging.warning((f'Requested job with job guid: {job_guid} '
                                     f'resulted in a server error with response: {response}'))

                # Unknown / unhandled response is received
                else:
                    raise Exception(('Failed to recognize the status '
                                     f'of the job status request HTTP {request_status}'))

            except Exception as e:  # pylint: disable=invalid-name
                logging.error(f'Failed to recognize the status of job guid: {job_guid}',
                              exc_info=e)
                raise
            else:
                logging.info(f'Job {job_guid} has status {status}')
                return status

    #
    # Applications
    #
    def stop_app(self, app_guid):
        stopped = False
        try:
            app_info = self.controller_session.get(f'/v2/apps/{app_guid}')
            app = app_info.get('response_body').get('applicationEntity')
        except Exception as e:  # pylint: disable=invalid-name
            logging.error(('Failed to fetch the information '
                           f'about the application guid: {app_guid}'), exc_info=e)
            raise
        else:
            if app.get('state') != 'STOPPED':
                app['state'] = 'STOPPED'
                try:
                    operation_info = self.controller_session.put(f'/v2/apps/{app_guid}', json=app)
                    request_status = operation_info.get('http_status')
                    response = operation_info.get('response_body')

                    # The request to stop the application is submitted and accepted
                    if request_status == 201:
                        job_guid = operation_info.get('response_headers').get('job-id')
                        logging.info((f'The request to stop application {app_guid} is accepted. '
                                      f'Started monitoring job {job_guid}'))
                        job_status = self.get_job_status(job_guid, wait_for_finish=True)
                    else:
                        raise Exception((f'The request to stop application {app_guid} '
                                         f'received unhandled HTTP status {request_status} '
                                         f'with response: {response}'))

                except Exception as e:  # pylint: disable=invalid-name
                    logging.error(f'Failed to stop the application: {app_guid}',
                                  exc_info=e)
                    raise
                else:
                    if job_status == 'FINISHED':
                        stopped = True
                        logging.info(f'Stopped application {app_guid}')
                    else:
                        stopped = False
                        logging.info((f'Failed to stop application {app_guid}. '
                                      f'The operation status is {job_status}'))
            return stopped

    def unbind_app_from_route(self, route_guid, app_guid):
        unbound = False
        try:
            operation_info = self.controller_session.delete(
                f'/v2/routes/{route_guid}/apps/{app_guid}')
            request_status = operation_info.get('http_status')
            response = operation_info.get('response_body')

            # The request to unbind the application from route is submitted and accepted
            if request_status == 201:
                logging.info((f'The request to unbind application {app_guid} '
                              f'from route {route_guid} performed succesfully'))
                unbound = True
            else:
                raise Exception((f'The request to unbind application {app_guid} '
                                 f'from route {route_guid} received unhandled HTTP '
                                 f'status {request_status} with response: {response}'))
        except Exception as e:  # pylint: disable=invalid-name
            logging.error(f'Failed to unbind application {app_guid} from route {route_guid}',
                          exc_info=e)
            raise
        else:
            return unbound
    
    def delete_task(self, task_guid):
        try:
            operation_info = self.controller_session.delete(
                f'/tasks/{task_guid}')
            request_status = operation_info.get('http_status')
            response = operation_info.get('response_body')
            
            # The request to delete the application task is submitted and accepted
            if request_status == 204:
                logging.info((f'The request to delete application task {task_guid} '
                              'performed succesfully'))
                deleted = True
            else:
                raise Exception((f'The request to delete application task {task_guid} '
                                 f'received unhandled HTTP status {request_status} '
                                 f'with response: {response}'))
        except Exception as e:  # pylint: disable=invalid-name
            logging.error(f'Failed to delete application task {task_guid}',
                          exc_info=e)
            raise
        else:
            return deleted
        
    def delete_app_tasks(self, org_guid, space_guid, app_guid):
        org = self.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        app = space.get_app_by_guid(app_guid)
        tasks = app.tasks
        
        deleted = False
        try:
            if tasks.keys():
                for task_guid in tasks.keys():
                    deleted = self.delete_task(task_guid)
                    if deleted:
                        logging.info((f'Deleted task {task_guid} of application {app_guid}'
                                      f'in {org.name} / {space.name}'))
                    else:
                        raise Exception((f'Failed to delete task {task_guid} of '
                                         f'application {app.name} / {app_guid} '
                                         f'from in {org.name} / {space.name}'))
                logging.info(f'Deleted all application tasks of application {app.name} / {app.guid}')
            else:
                logging.info((f'No tasks are identified for application {app_guid} '
                              f'in {org.name} / {space.name}'))
                deleted = True
        except Exception as e:  # pylint: disable=invalid-name
            logging.error((f'Failed to delete tasks of application {app.name} / {app_guid}  '
                           f'from {org.name} / {space.name}'), exc_info=e)
            raise
        else:
            return deleted    

    def delete_app(self, app_guid):
        # For the normal and complete deletion use delete_app_gracefully()
        deleted = False
        try:
            operation_info = self.controller_session.delete(f'/v2/apps/{app_guid}')
            request_status = operation_info.get('http_status')
            response = operation_info.get('response_body')

            # The request to delete the application is submitted and accepted
            if request_status == 204:
                logging.info(f'The request to delete application {app_guid} performed succesfully')
                deleted = True
            else:
                raise Exception((f'The request to delete application {app_guid} '
                                 f'received unhandled HTTP status {request_status} '
                                 f'with response: {response}'))
        except Exception as e:  # pylint: disable=invalid-name
            logging.error(f'Failed to delete application {app_guid}',
                          exc_info=e)
            raise
        else:
            return deleted

    def delete_app_instance(self, app_guid, instance_guid):
        deleted = False
        try:
            operation_info = self.controller_session.delete(
                f'/v2/apps/{app_guid}/instances/{instance_guid}')
            request_status = operation_info.get('http_status')
            response = operation_info.get('response_body')

            # The request to delete the application instance is submitted and accepted
            if request_status == 204:
                logging.info((f'The request to delete application instance {instance_guid} '
                              f'of application {app_guid} performed succesfully'))
                deleted = True
            else:
                raise Exception((f'The request to delete application instance {instance_guid} '
                                 f'of application {app_guid} '
                                 f'received unhandled HTTP status {request_status} '
                                 f'with response: {response}'))
        except Exception as e:  # pylint: disable=invalid-name
            logging.error((f'Failed to delete application instance {instance_guid} '
                           f'of application {app_guid}'), exc_info=e)
            raise
        else:
            return deleted

    def delete_app_gracefully(self, org_guid, space_guid, app_guid):
        org = self.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        app = space.get_app_by_guid(app_guid)
        routes = app.routes

        deleted = False

        try:
            # Stop the application instances
            stopped = self.stop_app(app_guid)
            if stopped:
                # Unbind the application from routes
                logging.info((f'Succesfully stopped application {app.name} / {app_guid} '
                              f'in {org.name} / {space.name}'))
                unbound_from_route = False
                if routes:
                    for route_guid in routes:
                        unbound_from_route = self.unbind_app_from_route(route_guid, app_guid)
                else:
                    logging.info((f'No routes were associated '
                                  f'with application {app.name} / {app_guid}'))
                    unbound_from_route = True
                if unbound_from_route:
                    logging.info((f'Succesfully unbound application {app.name} / {app_guid} '
                                  f'from routes in {org.name} / {space.name}'))
                    
                    # Delete tasks of the application
                    deleted_tasks = self.delete_app_tasks(org_guid, space_guid, app_guid)
                    if deleted_tasks:
                        logging.info((f'Succesfully deleted tasks of '
                                      f'application {app.name} / {app_guid} '
                                      f'from routes in {org.name} / {space.name}'))

                        # Delete the application
                        deleted = self.delete_app(app_guid)
                        if deleted:
                            logging.info((f'Gracefully deleted application {app.name} / {app_guid} '
                                          f'from {org.name} / {space.name}'))
                        else:
                            raise Exception((f'Failed to delete application {app.name} / {app_guid} '
                                             f'from in {org.name} / {space.name}'))
                    else:
                        raise Exception((f'Failed to delete tasks of '
                                         f'application {app.name} / {app_guid} '
                                         f'from in {org.name} / {space.name}'))
                else:
                    raise Exception((f'Failed to unbind application {app.name} / {app_guid} '
                                     f'from routes in {org.name} / {space.name}'))
            else:
                raise Exception((f'Failed to stop application {app.name} / {app_guid} '
                                 f'in {org.name} / {space.name}'))
        except Exception as e:  # pylint: disable=invalid-name
            logging.error((f'Failed to gracefully delete application {app.name} / {app_guid}  '
                           f'from {org.name} / {space.name}'), exc_info=e)
            raise
        else:
            return deleted

    #
    # Service Instances
    #
    def delete_service_instance(self, service_instances_guid, **kwargs):
        kwargs.setdefault('async', True)
        deleted = False
        job_status = None

        if kwargs.get('async'):
            # Asynchronous deletion is valid for operations taking longer
            # than the request processing timeout
            try:
                params = {'async': 'True',
                          'accepts_incomplete': 'True'}

                operation_info = self.controller_session.delete(
                    f'/v2/service_instances/{service_instances_guid}',
                    params=params)

                request_status = operation_info.get('http_status')
                response = operation_info.get('response_body')

                # The request to delete the service instance is submitted and accepted
                if request_status == 202:
                    job_guid = operation_info.get(
                        'response_headers').get('job-id')
                    logging.info((f'The request to delete service instance {service_instances_guid}'
                                  ' is accepted. '
                                  f'Started monitoring job {job_guid}'))
                    while job_status not in ['FINISHED', 'FAILED', 'NOT FOUND', 'SERVER ERROR']:
                        job_status = self.get_job_status(job_guid)
                        logging.info((f'Monitoring job {job_guid}. '
                                      f'The current status is {job_status}'))
                        # Wait for 10 seconds before updating the job status
                        time.sleep(5)
                else:
                    raise Exception((f'The request to delete service instance '
                                     f'{service_instances_guid} '
                                     f'received unhandled HTTP status {request_status} '
                                     f'with response: {response}'))
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(f'Failed to delete service instance {service_instances_guid}',
                              exc_info=e)
                raise
            else:
                if job_status == 'FINISHED':
                    deleted = True
                    logging.info(f'Delete service instance {service_instances_guid}')
                else:
                    deleted = False
                    logging.info((f'Failed to delete service instance {service_instances_guid}. '
                                  f'The operation status is {job_status}'))
        else:
            # Synchronous deletion is valid for operations not exceeding
            # the request processing timeout
            try:
                operation_info = self.controller_session.delete(
                    f'/v2/service_instances/{service_instances_guid}')
                request_status = operation_info.get('http_status')
                response = operation_info.get('response_body')

                # The request to delete the service instance is submitted and accepted
                if request_status == 204:
                    logging.info(('The request to delete service instance '
                                  f'{service_instances_guid} performed succesfully'))
                    deleted = True
                else:
                    raise Exception((f'The request to delete service instance '
                                     f'{service_instances_guid} '
                                     f'received unhandled HTTP status {request_status} '
                                     f'with response: {response}'))
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(f'Failed to delete service instance {service_instances_guid}',
                              exc_info=e)
                raise
        return deleted

    def delete_service_instances(self, service_instance_guids):
        # The experimental method of massive instances deletion
        # Presumes async only deletion of service instances
        # The method may cause excessive database exclusive locks while dropping HDI containers

        job_guids = []
        params = {'async': 'True',
                  'accepts_incomplete': 'True'}

        for service_instances_guid in service_instance_guids:
            # Wait for 5 seconds before submitting a new service instance deletion request
            time.sleep(5)

            try:
                operation_info = self.controller_session.delete(
                    f'/v2/service_instances/{service_instances_guid}',
                    params=params)

                request_status = operation_info.get('http_status')
                response = operation_info.get('response_body')
                # The request to delete the service instance is submitted and accepted
                if request_status == 202:
                    job_guid = operation_info.get('response_headers').get('job-id')
                    job_guids.append(job_guid)
                    logging.info(('The request to delete service instance '
                                  f'{service_instances_guid} is accepted. '
                                  f'Started monitoring job {job_guid}'))
                else:
                    raise Exception(('The request to delete service instance '
                                     f'{service_instances_guid} '
                                     f'received unhandled HTTP status {request_status} '
                                     f'with response: {response}'))

            except Exception as e:  # pylint: disable=invalid-name
                logging.error(f'Failed to delete service instance {service_instances_guid}',
                              exc_info=e)
                raise

            else:

                try:
                    while bool(job_guids):
                        for job_guid in job_guids:
                            # Wait for 3 seconds before updating the job status
                            time.sleep(3)
                            job_status = self.get_job_status(job_guid)
                            logging.info(
                                f'Monitoring job {job_guid}. The current status is {job_status}')
                            if job_status in ['FINISHED', 'FAILED', 'NOT FOUND', 'SERVER ERROR']:
                                job_guids.remove(job_guid)
                                if job_status == 'FINISHED':
                                    logging.info(
                                        f'Deletion job {job_guid} is succesfully finished')
                                else:
                                    logging.info((f'Deletion job {job_guid} is not finished. '
                                                  f'The operation status is {job_status}'))
                            else:
                                pass

                except Exception as e:  # pylint: disable=invalid-name
                    logging.error('Failed to monitor service instance deletion jobs',
                                  exc_info=e)
                    raise

                else:
                    logging.info(('Finished monitoring of all submitted service instance '
                                  'deletion jobs'))

    #
    # Controller methods and helpers
    #
    @staticmethod
    def get_item_by_guid(entity: dict, guid):
        return next((entity[item] for item in entity if entity[item].guid == guid), None)

    @staticmethod
    def get_item_by_name(entity: dict, name):
        return next((entity[item] for item in entity if entity[item].name == name), None)

    def get_org_by_name(self, name):
        found_org = self.get_item_by_name(self.orgs, name)
        if not found_org:
            logging.warning(f'The organization information is not found for name {name}')
        return found_org

    def get_database_by_guid(self, guid):
        found_database = self.get_item_by_guid(self.databases, guid)
        if not found_database:
            logging.warning(f'The database information is not found for guid {guid}')
        return found_database

    def get_org_by_guid(self, guid):
        found_org = self.get_item_by_guid(self.orgs, guid)
        if not found_org:
            logging.warning(f'The org information is not found for guid {guid}')
        return found_org


class User:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, controller, raw_data):
        logging.debug(f'Loading the user information based on {raw_data}')

        self.controller = controller
        self._representation = None
        self._spaces_representation = None
        self._orgs_representation = None
        self._role_collections_representation = None

        # list of tuples (org_guid, space_guid) > easier to search
        self._audited_org_guids = []
        # list of tuples (org_guid, space_guid) > easier to search
        self._managed_org_guids = []
        # list of tuples (org_guid, space_guid) > easier to search
        self._managed_space_guids = []
        # list of tuples (org_guid, space_guid) > easier to search
        self._audited_space_guids = []
        # list of tuples (org_guid, space_guid) > easier to search
        self._developer_space_guids = []

        self._role_collections = []

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)

        user_entity = raw_data.get('userEntity')
        self.uaa_guid = user_entity.get('uaaGuid')
        self.name = user_entity.get('username')
        self.origin = user_entity.get('origin')
        self.active = user_entity.get('active')
        self.orphaned = user_entity.get('orphaned')
        logging.info(f'Loaded information about user {self.name} / {self.guid}')

    #
    # Lazy load user's role collections
    #
    @property
    def role_collections(self):
        return self._role_collections

    @role_collections.getter
    def role_collections(self):
        uaa_session = self.controller.uaa_session
        if not self._role_collections:
            try:
                params = {'deactivatedUser': 'True'}
                role_collections_info = uaa_session.get(
                    f'/sap/rest/user/name/{self.name}',
                    params=params)
                role_collections = role_collections_info.get('response_body').get(
                    'roleCollections')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(
                    f'Failed to fetch role collections of user {self.name} / {self.guid}',
                    exc_info=e)
                raise
            else:
                parsed_role_collections = role_collections if role_collections else []
                self._role_collections = parsed_role_collections
                logging.debug(('Loaded the information about role collections '
                              f'of user {self.name} / {self.guid}'))
        return self._role_collections

    @role_collections.setter
    def role_collections(self, role_collections):
        self._role_collections = role_collections

    #
    # Represent user's role collections for the Collector
    #
    @property
    def role_collections_representation(self):
        return self._role_collections_representation

    @role_collections_representation.getter
    def role_collections_representation(self):
        representation = []
        if self.role_collections:
            for role_collection in self.role_collections:
                representation.append(
                    self.representation + (role_collection,)
                )
        return representation

    @staticmethod
    def get_role_collections_representation_keys():
        user_representation_keys = User.get_representation_keys()
        role_collections_representation_keys = ['Role Collection Name']
        return user_representation_keys + role_collections_representation_keys

    #
    # Lazy load user's audited organization guids
    #
    @property
    def audited_org_guids(self):
        return self._audited_org_guids

    @audited_org_guids.getter
    def audited_org_guids(self):
        controller_session = self.controller.controller_session
        if not self._audited_org_guids:
            try:
                audited_orgs_info = controller_session.get(
                    f'/v2/users/{self.guid}/audited_organizations')
                audited_orgs = audited_orgs_info.get('response_body').get('organizations')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(('Failed to fetch audited organizations '
                               f'of user {self.name} / {self.guid}'),
                              exc_info=e)
                raise
            else:
                parsed_audited_org_guids = []
                for org in audited_orgs:
                    org_guid = org.get('metadata').get('guid')
                    parsed_audited_org_guids.append(org_guid)
                self._audited_org_guids = parsed_audited_org_guids
                logging.debug(('Loaded the information about audited organizations '
                               f'of user {self.name} / {self.guid}'))
        return self._audited_org_guids

    @audited_org_guids.setter
    def audited_org_guids(self, audited_org_guids):
        self._audited_org_guids = audited_org_guids

    #
    # Lazy load user's managed organization guids
    #
    @property
    def managed_org_guids(self):
        return self._managed_org_guids

    @managed_org_guids.getter
    def managed_org_guids(self):
        controller_session = self.controller.controller_session
        if not self._managed_org_guids:
            try:
                managed_orgs_info = controller_session.get(
                    f'/v2/users/{self.guid}/managed_organizations')
                managed_orgs = managed_orgs_info.get('response_body').get('organizations')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(('Failed to fetch managed organizations '
                               f'of user {self.name} / {self.guid}'),
                              exc_info=e)
                raise
            else:
                parsed_managed_org_guids = []
                for org in managed_orgs:
                    org_guid = org.get('metadata').get('guid')
                    parsed_managed_org_guids.append(org_guid)
                self._managed_org_guids = parsed_managed_org_guids
                logging.debug(('Loaded the information about managed organizations '
                               f'of user {self.name} / {self.guid}'))
        return self._managed_org_guids

    @managed_org_guids.setter
    def managed_org_guids(self, managed_org_guids):
        self._managed_org_guids = managed_org_guids

    #
    # Lazy load user's managed space guids
    #
    @property
    def managed_space_guids(self):
        return self._managed_space_guids

    @managed_space_guids.getter
    def managed_space_guids(self):
        controller_session = self.controller.controller_session
        if not self._managed_space_guids:
            try:
                managed_spaces_info = controller_session.get(
                    f'/v2/users/{self.guid}/managed_spaces')
                managed_spaces = managed_spaces_info.get('response_body').get('spaces')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(f'Failed to fetch managed spaces of user {self.name} / {self.guid}',
                              exc_info=e)
                raise
            else:
                parsed_managed_space_guids = []
                for space in managed_spaces:
                    space_guid = space.get('metadata').get('guid')
                    org_guid = space.get('spaceEntity').get('organization_guid')
                    parsed_managed_space_guids.append((org_guid, space_guid))
                self._managed_space_guids = parsed_managed_space_guids
                logging.debug(('Loaded the information about managed spaces '
                               f'of user {self.name} / {self.guid}'))
        return self._managed_space_guids

    @managed_space_guids.setter
    def managed_space_guids(self, managed_space_guids):
        self._managed_space_guids = managed_space_guids

    #
    # Lazy load user's audited space guids
    #
    @property
    def audited_space_guids(self):
        return self._audited_space_guids

    @audited_space_guids.getter
    def audited_space_guids(self):
        controller_session = self.controller.controller_session
        if not self._audited_space_guids:
            try:
                audited_spaces_info = controller_session.get(
                    f'/v2/users/{self.guid}/audited_spaces')
                audited_spaces = audited_spaces_info.get('response_body').get('spaces')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(f'Failed to fetch audited spaces of user {self.name} / {self.guid}',
                              exc_info=e)
                raise
            else:
                parsed_audited_space_guids = []
                for space in audited_spaces:
                    space_guid = space.get('metadata').get('guid')
                    org_guid = space.get('spaceEntity').get('organization_guid')
                    parsed_audited_space_guids.append((org_guid, space_guid))
                self._audited_space_guids = parsed_audited_space_guids
                logging.debug(('Loaded the information about audited spaces '
                               f'of user {self.name} / {self.guid}'))
        return self._audited_space_guids

    @audited_space_guids.setter
    def audited_space_guids(self, audited_space_guids):
        self._audited_space_guids = audited_space_guids

    #
    # Lazy load user's developer space guids
    #
    @property
    def developer_space_guids(self):
        return self._developer_space_guids

    @developer_space_guids.getter
    def developer_space_guids(self):
        controller_session = self.controller.controller_session
        if not self._developer_space_guids:
            try:
                developer_spaces_info = controller_session.get(
                    f'/v2/users/{self.guid}/developer_spaces')
                developer_spaces = developer_spaces_info.get('response_body').get('spaces')
            except Exception as e:  # pylint: disable=invalid-name
                logging.error(
                    f'Failed to fetch developer spaces of user {self.name} / {self.guid}',
                    exc_info=e)
                raise
            else:
                parsed_developer_space_guids = []
                for space in developer_spaces:
                    space_guid = space.get('metadata').get('guid')
                    org_guid = space.get('spaceEntity').get('organization_guid')
                    parsed_developer_space_guids.append((org_guid, space_guid))
                self._developer_space_guids = parsed_developer_space_guids
                logging.debug(('Loaded the information about developer spaces '
                               f'of user {self.name} / {self.guid}'))
        return self._developer_space_guids

    @developer_space_guids.setter
    def developer_space_guids(self, developer_space_guids):
        self._developer_space_guids = developer_space_guids

    #
    # Represent the user the Collector
    #
    @property
    def representation(self):
        return self._representation

    @representation.getter
    def representation(self):
        return (self.guid,
                self.uaa_guid,
                self.name,
                self.origin,
                self.active,
                self.orphaned)

    @staticmethod
    def get_representation_keys():
        return ['User GUID',
                'User UAA GUID',
                'User Name',
                'Origin',
                'Is Active',
                'Is Orphaned']

    #
    # Represent user's space mappings for the Collector
    #
    @property
    def spaces_representation(self):
        return self._spaces_representation

    @spaces_representation.getter
    def spaces_representation(self):
        def get_space_mappings(self, org_space_tuples, mapped_role):
            # Expected to have mapped_role in list
            # of ['SpaceManager', 'SpaceAuditor', 'SpaceDeveloper']
            mappings = []
            if bool(org_space_tuples):
                for org_space_tuple in org_space_tuples:
                    org_guid, space_guid = org_space_tuple
                    org = self.controller.get_org_by_guid(org_guid)
                    space = org.get_space_by_guid(space_guid)
                    user = self.representation
                    mapping = (
                        org.guid,
                        org.name,
                        space.guid,
                        space.name,
                        mapped_role
                    )
                    mapping_representation = user + mapping
                    mappings.append(mapping_representation)
            return mappings

        spaces_representation = []
        managed_spaces_representation = get_space_mappings(self,
                                                           self.managed_space_guids,
                                                           'SpaceManager')
        audited_spaces_representation = get_space_mappings(self,
                                                           self.audited_space_guids,
                                                           'SpaceAuditor')
        developer_spaces_representation = get_space_mappings(self,
                                                             self.developer_space_guids,
                                                             'SpaceDeveloper')

        spaces_representation = (spaces_representation
                                 + managed_spaces_representation
                                 + audited_spaces_representation
                                 + developer_spaces_representation)

        return spaces_representation

    @staticmethod
    def get_spaces_representation_keys():
        user_representation_keys = User.get_representation_keys()
        spaces_representation_keys = ['Organization GUID',
                                      'Organization Name',
                                      'Space GUID',
                                      'Space Name',
                                      'Role']
        return user_representation_keys + spaces_representation_keys

    #
    # Represent user's org mappings for the Collector
    #
    @property
    def orgs_representation(self):
        return self._orgs_representation

    @orgs_representation.getter
    def orgs_representation(self):
        def get_org_mappings(self, org_list, mapped_role):
            # Expected to have mapped_role in list of ['OrgManager', 'OrgAuditor']
            mappings = []
            if bool(org_list):
                for org_guid in org_list:
                    org = self.controller.get_org_by_guid(org_guid)
                    user = self.representation
                    mapping = (org.guid,
                               org.name,
                               mapped_role)
                    mapping_representation = user + mapping
                    mappings.append(mapping_representation)
            return mappings

        orgs_representation = []
        managed_orgs_representation = get_org_mappings(self,
                                                       self.managed_org_guids,
                                                       'OrgManager')
        audited_orgs_representation = get_org_mappings(self,
                                                       self.audited_org_guids,
                                                       'OrgAuditor')

        orgs_representation = (orgs_representation
                               + managed_orgs_representation
                               + audited_orgs_representation)

        return orgs_representation

    @staticmethod
    def get_org_representation_keys():
        user_representation_keys = User.get_representation_keys()
        orgs_representation_keys = ['Organization GUID',
                                    'Organization Name',
                                    'Role']
        return user_representation_keys + orgs_representation_keys
