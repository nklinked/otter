import logging
from components.tools.utils import epoch_to_datetime # pylint: disable=import-error


class ServiceInstance:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    def __init__(self, space, raw_data):
        logging.debug(f'Loading the service instance information based on {raw_data}')

        self.space = space
        self.controller = self.space.controller
        self.controller_session = self.controller.controller_session

        self._service_keys = {}
        self._hana_configuration = {}
        self._app_relations = {}
        self._representation = None
        self._app_relations_representation = None

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)

        service_instance_entity = raw_data.get('serviceInstanceEntity')
        self.name = service_instance_entity.get('name')
        self.parameters = service_instance_entity.get('parameters')

        last_operation = service_instance_entity.get('last_operation')
        self.last_operation_type = last_operation.get('type') if last_operation else None
        self.last_operation_state = last_operation.get('state') if last_operation else None

        last_operation_updated_at = (last_operation.get('updated_at')
                                     if last_operation
                                     else None)
        self.last_operation_updated_at = (epoch_to_datetime(last_operation_updated_at)
                                          if last_operation_updated_at
                                          else None)

        service_plan_guid = service_instance_entity.get('service_plan_guid')
        service_plan = (self.space.get_service_plan_by_guid(service_plan_guid)
                        if service_plan_guid
                        else None)
        self.service_plan = service_plan
        self.belongs_to_hana_broker = self.service_plan.name in ['hdi-shared',
                                                                 'sbss',
                                                                 'securestore',
                                                                 'schema']

        self.service = self.service_plan.service

        service_bindings = self.space.service_bindings
        self.service_bindings = list(
            (service_bindings[guid] for guid in service_bindings
             if service_bindings[guid].bound_service_instance_guid == self.guid))
        self.count_bindings = len(self.service_bindings)

        logging.info((f'Loaded information about service instance {self.name} / {self.guid} '
                      'from Controller'))

    #
    # Lazy load the service keys
    #
    @property
    def service_keys(self):
        return self._service_keys

    @service_keys.getter
    def service_keys(self):
        controller_session = self.controller_session
        if not self._service_keys:
            try:
                params = {'noServiceCredentials': 'true',
                          'q': f'service_instance_guid:{self.guid}'}
                service_keys_info = controller_session.get('/v2/service_keys', params=params)
                service_keys = service_keys_info.get('response_body').get('serviceKeys')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(('Failed to load the service_keys of '
                               f'service instance {self.name} / {self.guid}'), exc_info=e)
                raise
            else:
                parsed_service_keys = {}
                for service_key in service_keys:
                    service_key_guid = service_key.get('metadata').get('guid')
                    parsed_service_keys[service_key_guid] = ServiceKey(self, service_key)
                self._service_keys = parsed_service_keys
                logging.debug(('Loaded the information about service keys '
                               f'of service instance {self.name} / {self.guid}'))
        return self._service_keys

    @service_keys.setter
    def service_keys(self, service_keys):
        self._service_keys = service_keys

    #
    # Lazy load the information about the respective HDI container / schema
    #
    @property
    def hana_configuration(self):
        return self._hana_configuration

    @hana_configuration.getter
    def hana_configuration(self):
        controller = self.controller
        hana_broker_session = controller.hana_broker_session

        if self.belongs_to_hana_broker:
            if not self._hana_configuration:
                try:
                    hana_configuration_info = hana_broker_session.get(
                        f'/admin/service_instances/{self.guid}/instance_data')
                    operation_status = hana_configuration_info.get('http_status')
                    hana_configuration = hana_configuration_info.get('response_body')
                except Exception as e: # pylint: disable=invalid-name
                    logging.error(('Failed to load the HANA configuration '
                                   f'of service instance {self.name} / {self.guid}'), exc_info=e)
                    raise
                else:
                    # In case of failed creation of the service instance such a request to
                    # HANA Broker will produce a server error HTTP 500
                    if operation_status != 500:
                        database_id = hana_configuration.get('databaseId')
                        database = controller.get_database_by_guid(database_id)
                        container_schema = hana_configuration.get('containerName')
                        parsed_hana_configuration = {'database': database,
                                                     'container_schema': container_schema}
                    else:
                        parsed_hana_configuration = {}
                    self._hana_configuration = parsed_hana_configuration
                    logging.debug(('Loaded the HANA configuration (if any) '
                                   f'of service instance {self.name} / {self.guid}'))
        else:
            self._hana_configuration = {}
        return self._hana_configuration

    @hana_configuration.setter
    def hana_configuration(self, hana_configuration):
        self._hana_configuration = hana_configuration

    #
    # Lazy load the information about the service instance usage by apps
    #
    @property
    def app_relations(self):
        return self._app_relations

    @app_relations.getter
    def app_relations(self):
        if not self._app_relations:
            service_bindings = self.service_bindings

            count_bindings = len(service_bindings)
            count_non_di_mta_bindings = 0
            count_non_di_mta_references = 0
            count_di_builder_bindings = 0
            count_standalone_bindings = 0

            if count_bindings:
                for binding in service_bindings:
                    app = self.space.get_app_by_guid(binding.bound_app_guid)
                    if app.belongs_to_mta:
                        if app.name == 'di-builder' and app.mta_id == 'com.sap.devx.di.builder':
                            count_di_builder_bindings += 1
                        else:
                            count_non_di_mta_bindings += 1
                            if self.name in app.mta_services:
                                count_non_di_mta_references += 1
                    else:
                        count_standalone_bindings += 1

            self._app_relations = {'count_bindings': count_bindings,
                                   'count_non_di_mta_bindings': count_non_di_mta_bindings,
                                   'count_non_di_mta_references': count_non_di_mta_references,
                                   'count_di_builder_bindings': count_di_builder_bindings,
                                   'count_standalone_bindings':  count_standalone_bindings
            }
            logging.debug(
                f'Loaded the application relations of service instance {self.name} / {self.guid}')
        return self._app_relations

    @app_relations.setter
    def app_relations(self, app_relations):
        self._app_relations = app_relations

    #
    # Represent the service instance to app relations for the Collector
    #
    @property
    def app_relations_representation(self):
        return self._app_relations_representation

    @app_relations_representation.getter
    def app_relations_representation(self):
        return (self.count_bindings,
                self.app_relations.get('count_bindings') if self.app_relations else None,
                self.app_relations.get('count_non_di_mta_bindings') if self.app_relations else None,
                (self.app_relations.get('count_non_di_mta_references')
                 if self.app_relations
                 else None),
                self.app_relations.get('count_di_builder_bindings') if self.app_relations else None,
                self.app_relations.get('count_standalone_bindings') if self.app_relations else None,
                len(self.service_keys))

    @staticmethod
    def get_app_relations_keys():
        return ['Bindings Count',
                'Bindings to Apps Count',
                'Bindings to MTAs Count (except di-builder)',
                'References to MTAs Count (except di-builder)',
                'Bindings to di-builder Count',
                'Bindings to Standalone Apps Count',
                'Service Keys Count']

    #
    # Represent the service instance to the Collector
    #
    @property
    def representation(self):
        return self._representation

    @representation.getter
    def representation(self):
        hana_configuration = self.hana_configuration
        database = hana_configuration.get('database') if self.hana_configuration else None
        tenant_name = database.tenant_name if database else None
        container_schema = (hana_configuration.get('container_schema')
                            if self.hana_configuration
                            else None)

        return (self.space.org.guid,
                self.space.org.name,
                self.space.guid,
                self.space.name,
                self.guid,
                self.name,
                self.created_at,
                self.updated_at,
                self.last_operation_type,
                self.last_operation_state,
                self.last_operation_updated_at,
                self.service.label if self.service else None,
                self.service_plan.name if self.service_plan else None,
                self.parameters,
                self.belongs_to_hana_broker,
                tenant_name,
                container_schema)

    @staticmethod
    def get_representation_keys():
        return ['Org GUID',
                'Org Name',
                'Space GUID',
                'Space Name',
                'Service Instance GUID',
                'Service Instance Name',
                'Created At',
                'Updated At',
                'Last Operation Type',
                'Last Operation State',
                'Last Operation Time',
                'Service Label',
                'Service Plan Name',
                'Parameters',
                'Belongs to HANA Broker',
                'Tenant Name (for HANA)',
                'Container Schema (for HANA)']


class ServiceKey:

    def __init__(self, service_instance, raw_data):
        logging.debug((f'Loading the service key information based on {raw_data} '
                       f'for service instance {service_instance.name} / {service_instance.guid}'))

        self.service_instance = service_instance
        self._representation = None

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)
        service_key_entity = raw_data.get('serviceKeyEntity')
        self.name = service_key_entity.get('name')

        logging.info((f'Loaded information about service key {self.name} / {self.guid} '
                      'of service instance '
                      f'{self.service_instance.name} / {self.service_instance.guid}'))

    #
    # Represent the service key to the Collector
    #
    @property
    def representation(self):
        return self._representation

    @representation.getter
    def representation(self):
        return (self.guid,
                self.name,
                self.created_at,
                self.updated_at)

    @staticmethod
    def get_representation_keys():
        return ['Service Key GUID',
                'Service Key Name',
                'Service Key Created At',
                'Service Key Updated At']

    @staticmethod
    def get_blank_representation():
        return (None,
                None,
                None,
                None)


class ServiceBroker:
    # pylint: disable=too-few-public-methods

    def __init__(self, raw_data):
        logging.debug(f'Loading the service broker information based on {raw_data}')

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        service_broker_entity = raw_data.get('serviceBrokerEntity')
        self.name = service_broker_entity.get('name')
        self.broker_endpoint = service_broker_entity.get('broker_url')

        logging.info(f'Loaded information about service broker {self.name} / {self.guid}')


class Service:
    # pylint: disable=too-few-public-methods

    def __init__(self, space, raw_data):
        logging.debug(f'Loading the service information based on {raw_data}')

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        service_entity = raw_data.get('serviceEntity')
        # Unique ID => GUID ?
        # self.guid = service_entity.get('unique_id')
        self.description = service_entity.get('description')
        self.label = service_entity.get('label')
        self.tags = service_entity.get('tags')
        service_broker_guid = service_entity.get('service_broker_guid')
        self.service_broker = space.get_service_broker_by_guid(service_broker_guid)

        logging.info(f'Loaded information about service {self.label} / {self.guid}')


class ServicePlan:
    # pylint: disable=too-few-public-methods

    def __init__(self, space, raw_data):
        logging.debug(f'Loading the service plan information based on {raw_data}')

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        service_plan_entity = raw_data.get('servicePlanEntity')
        # Unique ID => GUID ?
        # self.guid = service_plan_entity.get('unique_id')
        self.name = service_plan_entity.get('name')
        self.description = service_plan_entity.get('description')
        service_guid = service_plan_entity.get('service_guid')
        self.service = space.get_service_by_guid(service_guid)

        logging.info(f'Loaded information about service plan {self.name} / {self.guid}')


class ServiceBinding:
    # pylint: disable=too-few-public-methods

    def __init__(self, space, raw_data):
        logging.debug(f'Loading the service binding information based on {raw_data}')

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)

        service_binding_entity = raw_data.get('serviceBindingEntity')

        # Identifying the referenced application immedeately leads
        # to stack overflow due to recursive calls.
        # Until the exact design requirements the ServiceBinding contains only
        # guids of ServiceInstance and Application.
        # A potential alternative of doing the calls to Service Bindings API for
        # every ServiceInstance and Application (quering the respective guid) looks suboptimal.

        self.bound_service_instance_guid = service_binding_entity.get('service_instance_guid')
        self.bound_app_guid = service_binding_entity.get('app_guid')

        # service_instance_guid = service_binding_entity.get(
        #     'service_instance_guid')
        # service_instance = space.get_service_instance_by_guid(
        #     service_instance_guid) if service_instance_guid else None
        # if not service_instance:
        #     logging.warning(
        #         f'No service instance information is found for binding guid {self.guid}')
        # self.bound_service_instance = service_instance
        #
        # app_guid = service_binding_entity.get('app_guid')
        # app = space.get_app_by_guid(app_guid) if app_guid else None
        # if not app:
        #     logging.warning(
        #         f'No application information is found for binding guid {self.guid}')
        # self.bound_app = app

        credentials = service_binding_entity.get('credentials')
        self.credentials_schema = credentials.get('schema') if credentials else None
        self.credentials_tenant = credentials.get('tenant_name') if credentials else None

        logging.info(f'Loaded information about service binding {self.guid}')

class UserProvidedServiceInstance:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    def __init__(self, space, raw_data):
        logging.debug(f'Loading the user-provided service instance information based on {raw_data}')

        self.space = space
        self.controller = self.space.controller
        self.controller_session = self.controller.controller_session

        self._representation = None

        metadata = raw_data.get('metadata')
        self.guid = metadata.get('guid')
        self.created_at = (epoch_to_datetime(metadata.get('created_at'))
                           if metadata.get('created_at')
                           else None)
        self.updated_at = (epoch_to_datetime(metadata.get('updated_at'))
                           if metadata.get('updated_at')
                           else None)

        service_instance_entity = raw_data.get('userProvidedServiceInstanceEntity')
        self.name = service_instance_entity.get('name')
        self.credentials = service_instance_entity.get('credentials')

        logging.info((f'Loaded information about user-provided service instance {self.name} / {self.guid} '
                      'from Controller'))
    
    #
    # Represent the user-provided service instance to the Collector
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
                self.created_at,
                self.updated_at,
                self.credentials)

    @staticmethod
    def get_representation_keys():
        return ['Org GUID',
                'Org Name',
                'Space GUID',
                'Space Name',
                'UPS Instance GUID',
                'UPS Instance Name',
                'Created At',
                'Updated At',
                'Credentials (JSON)']