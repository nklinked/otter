import logging
import json
from components.tools.utils import epoch_to_datetime # pylint: disable=import-error
from components.controller.application import Application # pylint: disable=import-error
# pylint: disable=import-error
from components.controller.service import (ServiceInstance,
                                           Service,
                                           ServicePlan,
                                           ServiceBroker,
                                           ServiceBinding,
                                           UserProvidedServiceInstance)


class Space:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, org, raw_data):
        try:
            logging.debug((f'Loading the space information based on {raw_data} '
                           f'from organization {org.name} / {org.guid}'))

            self.org = org
            self.controller = self.org.controller
            self.controller_session = self.controller.controller_session

            self.guid = raw_data.get('metadata').get('guid')
            self.name = raw_data.get('spaceEntity').get('name')
            self.execution_user = raw_data.get('spaceEntity').get('execution_user')
            self.created_at = epoch_to_datetime(raw_data.get('metadata').get('created_at'))
            self.updated_at = epoch_to_datetime(raw_data.get('metadata').get('updated_at'))

            # Lazy load the space content
            self._content = {}
            self._apps = {}
            self._service_brokers = {}
            self._services = {}
            self._service_plans = {}
            self._service_bindings = {}
            self._service_instances = {}
            self._ups_service_instances = {}

            logging.info((f'Loaded the information about space {self.name} / {self.guid} '
                          f'from organization {self.org.name} / {self.org.guid}'))
            
        except Exception as e: # pylint: disable=invalid-name
            logging.error(f'Failed to instantiate space by metadata {json.dumps(raw_data)}',
                          exc_info=e)
            raise

    #
    # Lazy load the space content
    #
    @property
    def content(self):
        return self._content

    @content.getter
    def content(self):
        controller_session = self.controller_session
        if not self._content:
            try:
                content_info = controller_session.get(f'/v2/spaces/{self.guid}/content')
                content = content_info.get('response_body')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(f'Failed to load the content of space {self.name}', exc_info=e)
                raise
            else:
                self._content = content
                logging.debug(f'Loaded the content of space {self.name} / {self.guid}')
        return self._content

    @content.setter
    def content(self, content):
        self._content = content

    #
    # Lazy load apps from the space content
    #
    @property
    def apps(self):
        return self._apps

    @apps.getter
    def apps(self):
        if not self._apps:
            parsed_apps = {}
            apps = self.content.get('applications')
            for app in apps:
                app_guid = app.get('metadata').get('guid')
                parsed_apps[app_guid] = Application(self, app)
            self._apps = parsed_apps
            logging.debug(f'Loaded the applications of space {self.name} / {self.guid}')
        return self._apps

    @apps.setter
    def apps(self, apps):
        self._apps = apps

    #
    # Lazy load services from the space content
    #
    @property
    def services(self):
        return self._services

    @services.getter
    def services(self):
        if not self._services:
            parsed_services = {}
            services = self.content.get('services')
            for service in services:
                service_guid = service.get('metadata').get('guid')
                parsed_services[service_guid] = Service(self, service)
            self._services = parsed_services
            logging.debug(f'Loaded the services of space {self.name} / {self.guid}')
        return self._services

    @services.setter
    def services(self, services):
        self._services = services

    #
    # Lazy load service plans from the space content
    #
    @property
    def service_plans(self):
        return self._service_plans

    @service_plans.getter
    def service_plans(self):
        if not self._service_plans:
            parsed_service_plans = {}
            service_plans = self.content.get('servicePlans')
            for plan in service_plans:
                service_plan_guid = plan.get('metadata').get('guid')
                parsed_service_plans[service_plan_guid] = ServicePlan(self, plan)
            self._service_plans = parsed_service_plans
            logging.debug(f'Loaded the services plans of space {self.name} / {self.guid}')
        return self._service_plans

    @service_plans.setter
    def service_plans(self, service_plans):
        self._service_plans = service_plans

    #
    # Lazy load service brokers from the space content
    #
    @property
    def service_brokers(self):
        return self._service_brokers

    @service_brokers.getter
    def service_brokers(self):
        if not self._service_brokers:
            parsed_service_brokers = {}
            service_brokers = self.content.get('serviceBrokers')
            for broker in service_brokers:
                service_broker_guid = broker.get('metadata').get('guid')
                parsed_service_brokers[service_broker_guid] = ServiceBroker(broker)
            self._service_brokers = parsed_service_brokers
            logging.debug(f'Loaded the services brokers of space {self.name} / {self.guid}')
        return self._service_brokers

    @service_brokers.setter
    def service_brokers(self, service_brokers):
        self._service_brokers = service_brokers

    #
    # Lazy load service bindings from the space content
    #
    @property
    def service_bindings(self):
        return self._service_bindings

    @service_bindings.getter
    def service_bindings(self):
        if not self._service_bindings:
            parsed_service_bindings = {}
            service_bindings = self.content.get('serviceBindings')
            for binding in service_bindings:
                binding_guid = binding.get('metadata').get('guid')
                parsed_service_bindings[binding_guid] = ServiceBinding(self, binding)
            self._service_bindings = parsed_service_bindings
            logging.debug(f'Loaded the service bindings of space {self.name} / {self.guid}')
        return self._service_bindings

    @service_bindings.setter
    def service_bindings(self, service_bindings):
        self._service_bindings = service_bindings

    #
    # Lazy load service instances from the space content
    #
    @property
    def service_instances(self):
        return self._service_instances

    @service_instances.getter
    def service_instances(self):
        if not self._service_instances:
            parsed_service_instances = {}
            service_instances = self.content.get('serviceInstances')
            for instance in service_instances:
                instance_guid = instance.get('metadata').get('guid')
                parsed_service_instances[instance_guid] = ServiceInstance(self, instance)
            self._service_instances = parsed_service_instances
            logging.debug(f'Loaded the service instances of space {self.name} / {self.guid}')
        return self._service_instances

    @service_instances.setter
    def service_instances(self, service_instances):
        self._service_instances = service_instances
    
    #
    # Lazy load user-provided service instances from the space content
    #
    @property
    def ups_service_instances(self):
        return self._ups_service_instances

    @ups_service_instances.getter
    def ups_service_instances(self):
        if not self._ups_service_instances:
            parsed_ups_service_instances = {}
            ups_service_instances = self.content.get('userProvidedServiceInstances')
            for instance in ups_service_instances:
                instance_guid = instance.get('metadata').get('guid')
                parsed_ups_service_instances[instance_guid] = UserProvidedServiceInstance(self, instance)
            self._ups_service_instances = parsed_ups_service_instances
            logging.debug(f'Loaded the service instances of space {self.name} / {self.guid}')
        return self._ups_service_instances

    @ups_service_instances.setter
    def ups_service_instances(self, ups_service_instances):
        self._ups_service_instances = ups_service_instances

    #
    # Space methods and helpers
    #
    @staticmethod
    def get_item_by_guid(entity: dict, guid):
        return next((entity[item] for item in entity if entity[item].guid == guid), None)

    @staticmethod
    def get_item_by_name(entity: dict, name):
        return next((entity[item] for item in entity if entity[item].name == name), None)

    def get_app_by_name(self, name):
        found_app = self.get_item_by_name(self.apps, name)
        if not found_app:
            logging.warning(
                f'The app information is not found for name {name}')
        return found_app

    def get_service_instance_by_name(self, name):
        found_service_instance = self.get_item_by_name(self.service_instances, name)
        if not found_service_instance:
            logging.warning(
                f'The service instance information is not found for name {name}')
        return found_service_instance

    def get_service_instance_by_guid(self, guid):
        found_service_instance = self.get_item_by_guid(
            self.service_instances, guid)
        if not found_service_instance:
            logging.warning(
                f'The service instance information is not found for guid {guid}')
        return found_service_instance
    
    def get_ups_service_instance_by_guid(self, guid):
        found_service_instance = self.get_item_by_guid(
            self.ups_service_instances, guid)
        if not found_service_instance:
            logging.warning(
                f'The user-provided service instance information is not found for guid {guid}')
        return found_service_instance

    def get_service_broker_by_guid(self, guid):
        found_service_broker = self.get_item_by_guid(
            self.service_brokers, guid)
        if not found_service_broker:
            logging.warning(
                f'The service broker information is not found for guid {guid}')
        return found_service_broker

    def get_service_plan_by_guid(self, guid):
        found_service_plan = self.get_item_by_guid(
            self.service_plans, guid)
        if not found_service_plan:
            logging.warning(
                f'The service broker information is not found for guid {guid}')
        return found_service_plan

    def get_service_by_guid(self, guid):
        found_service = self.get_item_by_guid(self.services, guid)
        if not found_service:
            logging.warning(
                f'The service information is not found for guid {guid}')
        return found_service

    def get_app_by_guid(self, guid):
        found_app = self.get_item_by_guid(self.apps, guid)
        if not found_app:
            logging.warning(
                f'The application information is not found for guid {guid}')
        return found_app
